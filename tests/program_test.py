import io
import unittest
from logging import (
    Logger,
    basicConfig,
    StreamHandler,
    Formatter,
    DEBUG,
    INFO,
    FATAL,
    getLogger,
)

from pprint import pprint
from encab.config import ProgramConfig
from encab.program import (
    LoggingProgramObserver,
    ExecutionContext,
    Program,
    ProgramState,
)


class ProgramTest(unittest.TestCase):
    logger: Logger
    loglevel: int

    @classmethod
    def setUpClass(cls) -> None:
        cls.loglevel = FATAL
        handler = StreamHandler()
        formatter = Formatter(
            "%(asctime)s %(levelname)-5.5s %(module)s %(program)s %(threadName)s: %(message)s"
        )
        handler.setFormatter(formatter)
        root = getLogger()
        root.addHandler(handler)
        root.setLevel(cls.loglevel)
        cls.logger = getLogger(__name__)
        cls.logger.setLevel(cls.loglevel)

    def setUp(self):
        self.context = ExecutionContext(
            {},
            LoggingProgramObserver("encab", self.logger, {"program": "encab"}),
        )

    def program(self, name, command=None, sh=None, startup_delay=None) -> Program:
        config = ProgramConfig.create(
            command=command, sh=sh, startup_delay=startup_delay, loglevel=self.loglevel
        )
        return Program(name, config, self.context)

    def test_start(self):
        program = self.program("test_start", command=["echo", "Test"])
        state = program.start()
        self.assertTrue(
            state in (ProgramState.RUNNING, ProgramState.SUCCEEDED), f"state: {state}"
        )
        state = program.join(10)
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_start_script(self):
        program = self.program("test_start_script", sh='echo "Test"')
        state = program.start()
        self.assertTrue(
            state in (ProgramState.RUNNING, ProgramState.SUCCEEDED), f"state: {state}"
        )
        state = program.join(10)
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_crash(self):
        program = self.program("test_crash", command=["echox", "Test"])
        state = program.start()
        self.assertEqual(ProgramState.CRASHED, state)

    def test_join(self):
        program = self.program("test_join", command="echo Test")
        program.start()
        state = program.join()
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_interrupt(self):
        program = self.program("test_interrupt", command="sleep 10")
        program.start()
        program.interrupt()
        state = program.join()
        self.assertEqual(ProgramState.STOPPED, state)

    def test_terminate(self):
        program = self.program("test_terminate", command="sleep 10")
        program.start()
        program.terminate()
        state = program.join()
        self.assertEqual(ProgramState.STOPPED, state)

    def test_join_wait(self):
        program = self.program("test_join_wait", command="echo test", startup_delay=0.1)
        state = program.start()
        self.assertEqual(ProgramState.WAITING, state)
        state = program.join_wait()
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_cancel(self):
        program = self.program("test_cancel", command="echo test", startup_delay=1)
        state = program.start()
        self.assertEqual(ProgramState.WAITING, state)
        state = program.interrupt()
        state = program.join_wait()
        self.assertEqual(ProgramState.CANCELED, state)
