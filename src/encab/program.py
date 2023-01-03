import sys
import os
import signal

from io import IOBase
from copy import deepcopy

from typing import Dict, Optional, List, Tuple
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
        self.command = self.config.command
        
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
            state.wait(self.config.startup_delay)
            observer.on_execution(command, env, self.config)
            state.set(ProgramState.STARTING)
                        
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
                state.set(ProgramState.RUNNING)
                self._process = process
                
                observer.on_run(process.pid)
                
                LogStream(logger, ERROR, process.stderr, extra).start()
                LogStream(logger, INFO, process.stdout, extra).start()

                process.wait()
                state.handle_exit(process.returncode, self.command)
        except ProgramCanceledException as e:
            observer.on_cancel()
            state.set(ProgramState.CANCELED)
        except BaseException as e:
            observer.on_crash(self.command, e)
            state.set(ProgramState.CRASHED)
        finally:
            self._process = None

    def get_state(self) -> int:
        return self._state_handler.get()

    def start(self, timeout: float = 1) -> int:        
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

    def interrupt(self)  -> ProgramState:
        return self._state_handler.kill(self._process, SIGINT)

    def terminate(self) -> ProgramState:
        return self._state_handler.kill(self._process, SIGTERM)

    def join_wait(self, timeout: Optional[float] = None) -> ProgramState:
        return self._state_handler.join_wait(timeout)


'''
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
        except AbortedException as e:
            self.state.set(ProgramStates.CANCELED)
            self.observer.on_cancel()
        except PermissionError as e:
            self.state.set(ProgramStates.CRASHED)
            self.observer.on_crash(command, e)
        except OSError as e:
            self.state.set(ProgramStates.CRASHED)
            self.observer.on_crash(command, e)
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
'''
