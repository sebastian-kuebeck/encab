import os

from signal import SIGINT

from copy import deepcopy

from typing import Dict, Optional, List, Callable
from abc import ABC, abstractmethod

from enum import IntEnum
from subprocess import Popen
from threading import Condition

from logging import Logger, INFO, ERROR

from .config import ProgramConfig


class ProgramObserver(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def spawn(
        self, name: str, logger: Logger, extra: Dict[str, str]
    ) -> "ProgramObserver":
        pass

    @abstractmethod
    def on_state_change(self, state: int):
        pass

    @abstractmethod
    def on_received_state_change(self, state: int):
        pass

    @abstractmethod
    def on_wait_timeout(self, elapsed_time: float):
        pass

    @abstractmethod
    def on_start(self):
        pass

    @abstractmethod
    def on_execution(self, cmd: List[str], env: Dict[str, str], config: ProgramConfig):
        pass

    @abstractmethod
    def on_wait(self, startup_time: float):
        pass

    @abstractmethod
    def on_run(self, pid: int):
        pass

    @abstractmethod
    def on_exit(self, rc: int):
        pass

    @abstractmethod
    def on_terminate(self, pid: int):
        pass

    @abstractmethod
    def on_interrupt(self, pid: int):
        pass

    @abstractmethod
    def on_stopped(self):
        pass

    @abstractmethod
    def on_cancel(self):
        pass

    @abstractmethod
    def on_crash(self, cmd: List[str], e: BaseException):
        pass


class LoggingProgramObserver(ProgramObserver):
    def __init__(self, name: str, logger: Logger, extra: Dict[str, str]) -> None:
        self.name = name
        self.logger = logger
        self.extra = extra

    def get_name(self) -> str:
        return self.name

    def spawn(
        self, name: str, logger: Logger, extra: Dict[str, str]
    ) -> ProgramObserver:
        return LoggingProgramObserver(name, logger, deepcopy(extra))

    def on_state_change(self, state: int):
        self.logger.debug("Changing state to %s", state, extra=self.extra)

    def on_received_state_change(self, state: int):
        self.logger.debug("Changing state to %s", str(state), extra=self.extra)

    def on_wait_timeout(self, elapsed_time: float):
        self.logger.debug(
            "Wait timed out after %f seconds", elapsed_time, extra=self.extra
        )

    def on_start(self):
        self.logger.debug("Waiting for the program to start...", extra=self.extra)

    def on_execution(self, cmd: List[str], env: Dict[str, str], config: ProgramConfig):
        self.logger.debug("Executing %s", str(cmd), extra=self.extra)
        self.logger.debug(
            "Environment %s",
            str(env),
            extra=self.extra,
        )

        self.logger.debug("Config: %s", str(config), extra=self.extra)

        if config.user:
            self.logger.debug("User id: %d", config.user, extra=self.extra)

        if config.umask:
            self.logger.debug(
                "umask: 0o%s", format(config.umask, "o"), extra=self.extra
            )

    def on_wait(self, startup_time: float):
        self.logger.debug(
            "Waiting %1.2f seconds to start...", startup_time, extra=self.extra
        )

    def on_run(self, pid: int):
        self.logger.debug("Process pid %d", pid, extra=self.extra)

    def on_exit(self, rc: int):
        self.logger.log(
            ERROR if rc else INFO, "Exited with rc: %d", rc, extra=self.extra
        )

    def on_terminate(self, pid: int):
        self.logger.debug("Terminating process %d", pid, extra=self.extra)

    def on_interrupt(self, pid: int):
        self.logger.debug("Interrupting process %d", pid, extra=self.extra)

    def on_stopped(self):
        self.logger.info("Program has stopped.", extra=self.extra)

    def on_cancel(self):
        self.logger.info("Program start canceled.", extra=self.extra)

    def on_crash(self, cmd: List[str], e: BaseException):
        self.logger.error(
            "Failed to execute command %s: %s", str(e), str(cmd), extra=self.extra
        )


class ProgramCanceledException(Exception):
    pass


class ProgramCrashedException(Exception):
    pass


class ProgramState(IntEnum):
    """
    State of a Process within a Program

    +------------+-------+----------------------------------------+
    | Symbol     | Value | Description                            |
    +============+=======+========================================+
    | INIT       | 0     | Process is initialized                 |
    +------------+-------+----------------------------------------+
    | WAITING    | 1     | Process is waiting to start            |
    +------------+-------+----------------------------------------+
    | STARTING   | 2     | Process is starting                    |
    +------------+-------+----------------------------------------+
    | TIMEOUT    | 3     | Process start timet out                |
    +------------+-------+----------------------------------------+
    | RUNNING    | 4     | Process is running                     |
    +------------+-------+----------------------------------------+
    | CANCELING  | 6     | The Process start is being canceled    |
    +------------+-------+----------------------------------------+
    | STOPPING   | 5     | The Process was terminated by encab    |
    +------------+-------+----------------------------------------+
    | CANCELED   | 6     | Process start is being canceled        |
    +------------+-------+----------------------------------------+
    | CRASHED    | 6     | Process crashed during start           |
    +------------+-------+----------------------------------------+
    | STOPPED    | 7     | The Process was terminated by encab    |
    +------------+-------+----------------------------------------+
    | FAILED     | 8     | Process ended with rc != 0             |
    +------------+-------+----------------------------------------+
    | SUCCEEDED  | 9     | Process succeeded with rc = 0          |
    +------------+-------+----------------------------------------+
    | CANCELED   | 10    | Process execution was canceled         |
    +------------+-------+----------------------------------------+
    """

    INIT = 0
    WAITING = 1
    STARTING = 2
    RUNNING = 3

    CANCELING = 4
    STOPPING = 5

    CANCELED = 6
    CRASHED = 7
    STOPPED = 8
    FAILED = 9
    SUCCEEDED = 10


class ProgramStateHandler(object):
    def __init__(self, observer: ProgramObserver) -> None:
        super().__init__()
        self._state = ProgramState.INIT
        self._cond = Condition()
        self._observer = observer

    def set(self, state: ProgramState) -> None:
        with self._cond:
            self._observer.on_state_change(state)
            self._state = state
            self._cond.notify_all()

    def get(self) -> ProgramState:
        with self._cond:
            return self._state

    def wait_for(
        self, condition: Callable[[int], bool], timeout: Optional[float] = None
    ) -> ProgramState:
        with self._cond:
            condition_met = self._cond.wait_for(lambda: condition(self._state), timeout)
            if not condition_met:
                self._observer.on_wait_timeout(timeout or -1)
            return self._state

    def wait_for_startup(self, timeout: Optional[float] = None) -> ProgramState:
        return self.wait_for(
            lambda state: state == ProgramState.WAITING
            or state >= ProgramState.RUNNING,
            timeout,
        )

    def join(self, timeout: Optional[float] = None) -> ProgramState:
        return self.wait_for(
            lambda state: state == ProgramState.WAITING
            or state >= ProgramState.CANCELED,
            timeout,
        )

    def join_wait(self, timeout: Optional[float] = None) -> ProgramState:
        return self.wait_for(
            lambda state: state >= ProgramState.CANCELED,
            timeout,
        )

    def wait(self, timeout: float = 0) -> None:
        def canceled():
            return self._state >= ProgramState.CANCELING

        with self._cond:
            if timeout == 0 or self._state >= ProgramState.STARTING:
                return

            self._state = ProgramState.WAITING
            self._cond.notify_all()

            self._observer.on_wait(timeout)
            was_canceled = self._cond.wait_for(canceled, timeout)

            if was_canceled:
                raise ProgramCanceledException()

    def handle_exit(self, exit_code: int, command: List[str]):
        if exit_code == 0:
            self._observer.on_exit(exit_code)
            self.set(ProgramState.SUCCEEDED)
            return

        state = self.get()
        if state == ProgramState.RUNNING:
            self._observer.on_exit(exit_code)
            self.set(ProgramState.FAILED)
        elif state == ProgramState.STOPPING:
            self._observer.on_stopped()
            self.set(ProgramState.STOPPED)
        else:
            self._observer.on_crash(
                command,
                ProgramCrashedException(f"State: {state}, exit code {exit_code}"),
            )
            self.set(ProgramState.CRASHED)

    def kill(self, process: Optional[Popen], signal):
        with self._cond:
            if self._state >= ProgramState.CANCELED:
                return

            if self._state == ProgramState.WAITING:
                self._state = ProgramState.CANCELING
            else:
                self._state = ProgramState.STOPPING
                pid = process.pid if process else None
                if pid:
                    if signal == SIGINT:
                        self._observer.on_interrupt(pid)
                    else:
                        self._observer.on_terminate(pid)

                    try:
                        os.kill(pid, signal)
                    except ProcessLookupError:
                        pass

            self._cond.notify_all()
