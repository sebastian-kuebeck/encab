from copy import deepcopy

from typing import Dict, Optional, Union, List

from subprocess import Popen
from threading import Thread
from signal import SIGINT, SIGTERM

from logging import Logger, getLogger

from .common.process import Process
from .config import ProgramConfig
from .program_state import (
    ProgramObserver,
    ProgramState,
    ProgramStateHandler,
    ProgramCanceledException,
)
from .extensions import extensions


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
        self._process: Optional[Process] = None
        self.exit_code: Optional[int] = None

    def _run(self) -> None:
        logger = self.logger
        extra = self.extra

        command = self.command
        env = self.context.environment
        state = self._state_handler
        observer = self._observer

        startup_delay = self.config.startup_delay

        umask = self.config.umask
        user = self.config.user
        group = self.config.group
        cwd = self.config.directory
        reap_zombies = self.config.reap_zombies

        assert user is None or isinstance(user, int)
        assert group is None or isinstance(group, int)
        assert isinstance(reap_zombies, bool)

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

            def on_run(popen: Popen):
                state.set(ProgramState.RUNNING)
                observer.on_run(popen.pid)

            self._process = Process(
                args,
                env,
                user=user,
                group=group,
                umask=umask,
                shell=shell,
                start_new_session=True,
                cwd=cwd,
                reap_zombies=reap_zombies,
            )
            self.exit_code = self._process.execute_and_log(on_run, logger, extra)
            state.handle_exit(self.exit_code, self.command)
        except ProgramCanceledException:
            observer.on_cancel()
            state.set(ProgramState.CANCELED)
        except BaseException as e:
            observer.on_crash(self.command, e)
            state.set(ProgramState.CRASHED)

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
        return self._state_handler.signal(self._process, SIGINT)

    def terminate(self) -> None:
        return self._state_handler.signal(self._process, SIGTERM)

    def join_wait(self, timeout: Optional[float] = None) -> ProgramState:
        return self._state_handler.join_wait(timeout)
