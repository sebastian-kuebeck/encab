import sys
import os
import signal

from io import IOBase
from copy import deepcopy

from typing import Dict, Optional, List, Tuple, cast
from abc import ABC, abstractmethod

from enum import IntEnum
from subprocess import Popen, PIPE
from threading import Thread
from signal import SIGINT, SIGTERM

from logging import Logger, DEBUG, INFO, ERROR, getLogger, Formatter, StreamHandler

from .config import ProgramConfig
from .program_state import (
    ProgramObserver,
    LoggingProgramObserver,
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
        self, logger: Logger, log_level: int, stream: IOBase, extra: Dict[str, str]
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
                strline = line.decode(sys.getdefaultencoding()).rstrip("\r\n\t\ ")
                self.logger.log(self.log_level, strline, extra=self.extra)
        except ValueError:
            pass  # stream was closed
        except OSError as e:
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
            self.command = cast(List[str], self.config.command)
        else:
            self.shell = True
            self.command = [cast(str, self.config.sh)]

        observer = self.context.observer

        self._observer = observer
        self._state_handler = ProgramStateHandler(observer)
        self._process: Optional[Popen] = None

    def _run(self):
        logger = self.logger
        extra = self.extra
        command = self.command
        env = self.context.environment
        state = self._state_handler
        observer = self._observer

        try:
            state.wait(cast(float, self.config.startup_delay))
            observer.on_execution(cast(List[str], command), env, self.config)
            state.set(ProgramState.STARTING)

            shell = self.shell
            if shell:
                command = command[0]

            with Popen(
                command,
                stdout=PIPE,
                stderr=PIPE,
                env=env,
                user=self.config.user,
                umask=cast(int, self.config.umask),
                shell=shell,
                start_new_session=True,
            ) as process:
                state.set(ProgramState.RUNNING)
                self._process = process

                observer.on_run(process.pid)

                LogStream(logger, ERROR, cast(IOBase, process.stderr), extra).start()
                LogStream(logger, INFO, cast(IOBase, process.stdout), extra).start()

                process.wait()
                state.handle_exit(process.returncode, cast(List[str], self.command))
        except ProgramCanceledException as e:
            observer.on_cancel()
            state.set(ProgramState.CANCELED)
        except BaseException as e:
            observer.on_crash(cast(List[str], self.command), e)
            state.set(ProgramState.CRASHED)
        finally:
            self._process = None

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
