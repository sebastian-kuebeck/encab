import sys

from copy import deepcopy

from typing import Dict, Optional, IO, Union, List

from subprocess import Popen, PIPE
from threading import Thread
from signal import SIGINT, SIGTERM

from logging import Logger, INFO, ERROR, getLogger

from .config import ProgramConfig
from .program_state import (
    ProgramObserver,
    ProgramState,
    ProgramStateHandler,
    ProgramCanceledException,
)
from .extensions import extensions


class LogStream(object):
    """
    Reads from a stream in a background thread and loggs the result line by line
    """

    def __init__(
        self, logger: Logger, log_level: int, stream: IO[bytes], extra: Dict[str, str]
    ) -> None:
        """
        :param Logger logger: the logger to which the stream content is written
        :param int log_level: the log level (see Python logging)
        :param IOBase stream: the stream that is logged
        :param Dict[str, str] extra: extra information that is logged each line (see Python logging)
        """
        self.logger = logger
        self.log_level = log_level
        self.stream = stream
        self.extra = extra
        self.thread: Optional[Thread] = None

    def _run(self):
        try:
            for line in self.stream:
                strline = line.decode(sys.getdefaultencoding()).rstrip("\r\n\t ")
                self.logger.log(self.log_level, strline, extra=self.extra)
        except ValueError:
            pass  # stream was closed
        except OSError:
            self.logger.exception(
                "I/O Error while logging: %s", self.name, extra=self.extra  # type: ignore
            )
        except:
            self.logger.exception(
                "Something went wrong while logging", extra=self.extra
            )
            raise

    def start(self):
        """starts reading and logging"""
        program = self.extra.get("program", "")
        name = f"{program}:{self.log_level}"
        thread = Thread(target=lambda: self._run(), name=name)
        thread.daemon = True
        self.thread = thread
        thread.start()
        return self

    def close(self):
        try:
            self.stream.flush()
        except IOError:
            pass
        self.stream.close()


class ExecutionContext(object):
    """
    The context in which a program is executed

    It contains all non-static resources necessary to execute a program,
    such as the logger and the system environment.
    """

    def __init__(self, environment: Dict[str, str], observer: ProgramObserver) -> None:
        self.environment = environment
        self.observer = observer
        extensions.extend_environment(observer.get_name(), environment)

    def extend(self, environment: Dict[str, str]) -> "ExecutionContext":
        env = deepcopy(self.environment)
        if environment:
            env.update(environment)
            extensions.extend_environment(self.observer.get_name(), self.environment)

        return ExecutionContext(env, self.observer)

    def spawn(
        self,
        name: str,
        environment: Dict[str, str],
        logger: Logger,
        extra: Dict[str, str],
    ) -> "ExecutionContext":
        env = deepcopy(self.environment)
        observer = self.observer.spawn(name, logger, extra)

        if environment:
            extensions.extend_environment(name, self.environment)
            env.update(environment)

        extensions.update_logger(name, logger)
        return ExecutionContext(env, observer)


class Program(object):
    """
    Starts a program and caputures stdout and sterr as log messages
    """

    def __init__(
        self, name: str, config: ProgramConfig, parent_context: ExecutionContext
    ) -> None:
        """
        :name: (str)
            the program name
        :config: (ProgramConfig)
            the program configuration
        :parent_context (ExecutionContext):
            the parent program execution context
        """
        self.name = name
        self.config = config

        self.logger = getLogger(__name__)

        if config.loglevel:
            self.logger.setLevel(config.loglevel)

        self.extra = {"program": name}
        self.context: ExecutionContext = parent_context.spawn(
            name, self.config.environment or {}, self.logger, self.extra
        )

        if self.config.command:
            self.shell = False
            assert isinstance(self.config.command, list)
            self.command = self.config.command
        else:
            self.shell = True
            assert isinstance(self.config.sh, str)
            self.command = [self.config.sh]

        observer = self.context.observer

        self._observer = observer
        self._state_handler = ProgramStateHandler(observer)
        self._process: Optional[Popen] = None

    def _run(self) -> None:
        logger = self.logger
        extra = self.extra
        command = self.command
        env = self.context.environment
        state = self._state_handler
        observer = self._observer
        startup_delay = self.config.startup_delay
        umask = self.config.umask
        out: Optional[LogStream] = None
        err: Optional[LogStream] = None

        try:
            assert isinstance(startup_delay, float) or isinstance(startup_delay, int)
            assert isinstance(umask, int)

            state.wait(float(startup_delay))

            observer.on_execution(command, env, self.config)
            state.set(ProgramState.STARTING)

            shell = self.shell
            args: Union[str, List[str]] = command

            if shell:
                args = command[0]

            process = Popen(
                args,
                stdout=PIPE,
                stderr=PIPE,
                env=env,
                user=self.config.user,
                umask=umask,
                shell=shell,
                start_new_session=True,
            )
            assert process.stdout is not None
            assert process.stderr is not None

            state.set(ProgramState.RUNNING)
            self._process = process

            observer.on_run(process.pid)

            err = LogStream(logger, ERROR, process.stderr, extra).start()
            out = LogStream(logger, INFO, process.stdout, extra).start()

            process.wait()
            state.handle_exit(process.returncode, self.command)
        except ProgramCanceledException:
            observer.on_cancel()
            state.set(ProgramState.CANCELED)
        except BaseException as e:
            observer.on_crash(self.command, e)
            state.set(ProgramState.CRASHED)
        finally:
            self._process = None
            if out:
                out.close()
            if err:
                err.close()

    def get_state(self) -> int:
        return self._state_handler.get()

    def start(self, timeout: Optional[float] = 1) -> int:
        thread = Thread(target=lambda: self._run(), name=self.name)
        thread.daemon = True
        thread.start()

        self._observer.on_start()

        return self._state_handler.wait_for_startup(timeout)

    def join(
        self,
        timeout: Optional[float] = None,
    ) -> ProgramState:
        return self._state_handler.join(timeout)

    def interrupt(self) -> None:
        return self._state_handler.kill(self._process, SIGINT)

    def terminate(self) -> None:
        return self._state_handler.kill(self._process, SIGTERM)  # type: ignore

    def join_wait(self, timeout: Optional[float] = None) -> ProgramState:
        return self._state_handler.join_wait(timeout)
