import sys
import os
import signal

from io import IOBase
from copy import deepcopy

from typing import Dict, Optional, List, Tuple
from abc import ABC, abstractmethod

from enum import IntEnum
from subprocess import Popen, PIPE
from threading import Thread, Lock
from queue import Queue, Empty

from logging import Logger, DEBUG, INFO, ERROR, getLogger

from .config import ProgramConfig


class ProgramObserver(ABC):
    @abstractmethod
    def spawn(self, logger: Logger, extra: Dict[str, str]) -> "ProgramObserver":
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
    def on_cancel(self, e: Exception):
        pass

    @abstractmethod
    def on_crash(self, cmd: List[str], e: Exception):
        pass


class LoggingProgramObserver(ProgramObserver):
    def __init__(self) -> None:
        self.logger = getLogger(__name__)
        self.extra = {"program": "encab"}

    def spawn(self, logger: Logger, extra: Dict[str, str]) -> ProgramObserver:
        observer = LoggingProgramObserver()
        observer.logger = logger
        observer.extra = deepcopy(extra)
        return observer

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

    def on_cancel(self, e: Exception):
        self.logger.debug("Program start canceled.", extra=self.extra)

    def on_crash(self, cmd: List[str], e: Exception):
        self.logger.error(
            "Failed to execute command %s: %s", str(e), str(cmd), extra=self.extra
        )


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
                "I/O Error while logging: %s", self.name, extra=self.extra
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


class ProgramStates(IntEnum):
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
    | STOPPING   | 5     | The Process was terminated by encab    |
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
    TIMEOUT = 3
    RUNNING = 4
    STOPPING = 5
    CRASHED = 6
    STOPPED = 7
    FAILED = 8
    SUCCEEDED = 9
    CANCELED = 10


class AbortedException(Exception):
    pass


class ProgramState(object):
    """represents the current programs state and operations on it"""

    def __init__(self, observer: ProgramObserver) -> None:
        """creates a new program state

        :param observer: the observer
        :type observer: ProgramObserver
        """
        self.observer = observer
        self.lock = Lock()
        self.state: int = ProgramStates.INIT
        self.queue: Queue = Queue()

    def set(self, state: int) -> None:
        """
        sets the program state

        :param state: the target program state
        :type state: int
        :raises AbortedException: if the program is already stopping
        """

        with self.lock:
            if self.state == ProgramStates.STOPPING and state <= ProgramStates.RUNNING:
                raise AbortedException()

            self.observer.on_state_change(state)

            self.state = state

        self.queue.put(state)

    def get(self) -> int:
        """
        returns the current prgram state
        :return: the state
        :rtype: int
        """
        with self.lock:
            return self.state

    def wait(self, min_state: int, timeout: Optional[float]) -> int:
        """waits untill an expected state is reached

        :param min_state: the minimum state to be reached
        :type min_state: int
        :param timeout: the wait timeout in seconds. If it is None, the method waits forever if necessary. Default: None
        :type timeout: Optional[float]
        :return: the state reached
        :rtype: int
        """
        while True:
            try:
                state = self.queue.get(timeout=timeout)
                self.observer.on_received_state_change(state)
                if state >= min_state:
                    return state
            except Empty:
                self.observer.on_wait_timeout(timeout or -1)
                return ProgramStates.TIMEOUT

    def sleep(self, startup_time: float):
        try:
            with self.lock:
                if self.state >= ProgramStates.CRASHED:
                    raise AbortedException()

                state = ProgramStates.WAITING
                self.observer.on_state_change(state)
                self.state = state

            self.observer.on_wait(startup_time)

            while True:
                state = self.queue.get(timeout=startup_time)
                if state >= ProgramStates.RUNNING:
                    raise AbortedException()
        except Empty:
            pass

    def was_stopped(self) -> bool:
        with self.lock:
            return self.state in (ProgramStates.STOPPING, ProgramStates.STOPPED)

    def has_ended(self) -> bool:
        with self.lock:
            return self.state >= ProgramStates.CRASHED

    def is_running_or_stopping(self) -> bool:
        with self.lock:
            return self.state in (ProgramStates.RUNNING, ProgramStates.STOPPING)

    def send(self, process: Optional[Popen], the_signal):
        with self.lock:
            if self.state >= ProgramStates.STOPPED:
                return
            else:
                pid = process.pid if process else None
                if pid:
                    if the_signal == signal.SIGINT:
                        self.observer.on_interrupt(pid)
                    else:
                        self.observer.on_terminate(pid)

                    try:
                        os.kill(pid, the_signal)
                    except ProcessLookupError:
                        pass

            self.state = ProgramStates.STOPPING

        self.queue.put(ProgramStates.STOPPING)

    def terminate(self, process: Optional[Popen]):
        self.send(process, signal.SIGTERM)

    def interrupt(self, process: Optional[Popen]):
        self.send(process, signal.SIGINT)


class ExecutionContext(object):
    """
    The context in which a program is executed

    It contains all non-static resources necessary to execute a program,
    such as the logger and the system environment.
    """

    def __init__(
        self,
        environment: Optional[Dict[str, str]] = None,
        observer: Optional[ProgramObserver] = None,
    ) -> None:
        self.environment = environment or {}
        self.observer = observer or LoggingProgramObserver()

    def extend(self, environment: Optional[Dict[str, str]]) -> "ExecutionContext":
        environment = environment or {}
        env = deepcopy(self.environment)
        if environment:
            env.update(environment)
        return ExecutionContext(env, self.observer)

    def spawn(
        self,
        environment: Optional[Dict[str, str]],
        logger: Logger,
        extra: Dict[str, str],
    ) -> "ExecutionContext":
        environment = environment or {}
        env = deepcopy(self.environment)
        if environment:
            env.update(environment)
        return ExecutionContext(env, self.observer.spawn(logger, extra))


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
            self.config.environment, self.logger, self.extra
        )

        self.observer: ProgramObserver = self.context.observer
        self.state = ProgramState(self.observer)

        self.command = self.config.command
        self.process: Optional[Popen] = None

    def _run(self):
        try:
            self.state.set(ProgramStates.STARTING)
            logger = self.logger
            extra = self.extra
            command = self.command
            env = self.context.environment
            rc = 0

            if self.config.startup_delay > 0:
                self.state.sleep(self.config.startup_delay)

            self.observer.on_execution(command, env, self.config)

            with Popen(
                command,
                stdout=PIPE,
                stderr=PIPE,
                env=env,
                user=self.config.user,
                umask=self.config.umask,
                shell=self.config.shell,
                start_new_session=True,
            ) as process:
                self.state.set(ProgramStates.RUNNING)
                self.process = process
                self.observer.on_run(process.pid)
                LogStream(logger, ERROR, process.stderr, extra).start()
                LogStream(logger, INFO, process.stdout, extra).start()

                process.wait()

                rc = process.returncode

            if rc == 0:
                self.state.set(ProgramStates.SUCCEEDED)
                self.observer.on_exit(rc)
            else:
                if not self.state.was_stopped():
                    self.state.set(ProgramStates.FAILED)
                    self.observer.on_exit(rc)
                else:
                    self.state.set(ProgramStates.STOPPED)
                    self.observer.on_stopped()
        except PermissionError as e:
            self.state.set(ProgramStates.CRASHED)
            self.observer.on_crash(command, e)
        except OSError as e:
            self.state.set(ProgramStates.CRASHED)
            self.observer.on_crash(command, e)
        except AbortedException as e:
            self.state.set(ProgramStates.CANCELED)
            self.observer.on_cancel(e)
            logger.debug("Program start canceled.", extra=extra)
        except BaseException as e:
            self.state.set(ProgramStates.CRASHED)
            self.observer.on_crash(command, e)
            raise
        finally:
            self.process = None

    def start(
        self, timeout: Optional[float] = 10, min_state: int = ProgramStates.RUNNING
    ) -> int:
        """
        starts the program

        it starts the process based on the configuration and context
        and waits unitill its running.

        If the process immediately returns a result,
        the result is reflected in the return value.

        :param float timeout:
            the timeout. Defaults to 10 seconds.
        :param int min_state:
            minimum state that must be reached for the method to return
        :returns:
            the program state

        :rtype: int
        """

        thread = Thread(target=lambda: self._run(), name=self.name)
        thread.daemon = True
        thread.start()

        self.observer.on_start()

        delay = self.config.startup_delay or 0.0
        if timeout and delay > timeout / 2.0:
            return ProgramStates.WAITING

        return self.state.wait(min_state, timeout)

    def join(
        self,
        timeout: Optional[float] = None,
    ) -> int:
        if self.state.is_running_or_stopping():
            return self.state.wait(ProgramStates.CRASHED, timeout)
        else:
            return self.state.get()

    def terminate(self):
        self.state.terminate(self.process)

    def interrupt(self):
        self.state.interrupt(self.process)

    def has_ended(self) -> bool:
        return self.state.has_ended()
