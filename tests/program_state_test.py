import io
import unittest

from signal import SIGINT, SIGTERM

from logging import (
    Logger,
    basicConfig,
    StreamHandler,
    Formatter,
    DEBUG,
    INFO,
    getLogger,
)

from pprint import pprint


from typing import Optional, List, Tuple, Dict
from threading import Thread
from subprocess import Popen

from encab.config import ProgramConfig
from encab.program_state import (
    ProgramObserver,
    LoggingProgramObserver,
    ProgramState,
    ProgramStateHandler,
    ProgramCanceledException,
)


class TestProgramObserver(LoggingProgramObserver):
    def __init__(
        self, logger: Logger, parent: Optional["TestProgramObserver"] = None
    ) -> None:
        self.logger = logger
        self.parent = parent
        self.observer = self.parent or self
        self.name = "test"
        self.extra = {"program": "test"}

    def spawn(self, logger: Logger, extra: Dict[str, str]) -> ProgramObserver:
        observer = TestProgramObserver(logger, self)
        observer.extra = extra
        observer.name = extra["program"]
        return observer


class TestProgram(object):
    def __init__(
        self,
        name: str,
        command: List[str],
        observer: ProgramObserver,
        startup_delay: int = 0,
    ) -> None:
        self.name = name
        self.startup_delay = startup_delay
        self.command = command

        self._observer = observer
        self._state_handler = ProgramStateHandler(observer)
        self._process = None

    def _run(self):
        try:
            self._state_handler.wait(self.startup_delay)
            self._state_handler.set(ProgramState.STARTING)

            self._process = Popen(self.command)
            self._state_handler.set(ProgramState.RUNNING)
            self._process.wait()

            self._state_handler.handle_exit(self._process.returncode, self.command)
        except ProgramCanceledException as e:
            self._observer.on_cancel()
            self._state_handler.set(ProgramState.CANCELED)
        except BaseException as e:
            self._observer.on_crash(self.command, e)
            self._state_handler.set(ProgramState.CRASHED)

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
    ) -> int:
        return self._state_handler.join(timeout)

    def interrupt(self) -> ProgramState:
        return self._state_handler.kill(self._process, SIGINT)

    def terminate(self)  -> ProgramState:
        return self._state_handler.kill(self._process, SIGTERM)

    def join_wait(self, timeout: Optional[float] = None)  -> ProgramState:
        return self._state_handler.join_wait(timeout)


class ProgramStateTest(unittest.TestCase):
    logger: Logger

    @classmethod
    def setUpClass(cls) -> None:
        handler = StreamHandler()
        formatter = Formatter(
            "%(asctime)s %(levelname)-5.5s %(module)s %(program)s %(threadName)s: %(message)s"
        )
        handler.setFormatter(formatter)
        basicConfig(level=DEBUG, handlers=[handler])
        cls.logger = getLogger(__name__)

    def setUp(self) -> None:
        super().setUp()
        self.observer = TestProgramObserver(self.logger)

    def test_start(self):
        program = TestProgram("test_start", ["echo", "test"], self.observer)
        state = program.start()
        self.assertTrue(state in (ProgramState.RUNNING, ProgramState.SUCCEEDED))

    def test_join(self):
        program = TestProgram("test_join", ["echo", "test"], self.observer)
        program.start()
        state = program.join()
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_crash(self):
        program = TestProgram("test_crash", ["excho", "test"], self.observer)
        program.start()
        state = program.join()
        self.assertEqual(ProgramState.CRASHED, state)

    def test_interrupt(self):
        program = TestProgram("test_interrupt", ["sleep", "10"], self.observer)
        program.start()
        program.interrupt()
        state = program.join()
        self.assertEqual(ProgramState.STOPPED, state)

    def test_terminate(self):
        program = TestProgram("test_terminate", ["sleep", "10"], self.observer)
        program.start()
        program.terminate()
        state = program.join()
        self.assertEqual(ProgramState.STOPPED, state)

    def test_join_wait(self):
        program = TestProgram("test_join_wait", ["echo", "test"], self.observer, 0.1)
        state = program.start()
        self.assertEqual(ProgramState.WAITING, state)

        state = program.join_wait()
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_cancel(self):
        program = TestProgram("test_cancel", ["sleep", "10"], self.observer, 1)
        program.start()
        program.terminate()
        state = program.join_wait()
        self.assertEqual(ProgramState.CANCELED, state)
