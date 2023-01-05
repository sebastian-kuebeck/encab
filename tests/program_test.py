import io
import unittest
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
from encab.config import ProgramConfig
from encab.program import (
    LoggingProgramObserver,
    ExecutionContext,
    Program,
    ProgramState,
)


class ProgramTest(unittest.TestCase):
    logger: Logger

    @classmethod
    def setUpClass(cls) -> None:
        handler = StreamHandler()
        formatter = Formatter(
            "%(asctime)s %(levelname)-5.5s %(module)s %(program)s %(threadName)s: %(message)s"
        )
        handler.setFormatter(formatter)
        basicConfig(level=INFO, handlers=[handler])
        ProgramTest.logger = getLogger(__name__)

    def setUp(self):
        self.context = ExecutionContext(
            {},
            LoggingProgramObserver("encab", ProgramTest.logger, {"program": "encab"}),
        )

    def test_start(self):
        config = ProgramConfig.create(command='echo "Test"')
        program = Program("test_start", config, self.context)
        state = program.start()
        self.assertTrue(
            state in (ProgramState.RUNNING, ProgramState.SUCCEEDED), f"state: {state}"
        )
        state = program.join(10)
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_start_script(self):
        config = ProgramConfig.create(sh='echo "Test"')
        program = Program("test_start", config, self.context)
        state = program.start()
        self.assertTrue(
            state in (ProgramState.RUNNING, ProgramState.SUCCEEDED), f"state: {state}"
        )
        state = program.join(10)
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_crash(self):
        config = ProgramConfig.create(command='excho "Test"')
        program = Program("test_crash", config, self.context)
        state = program.start()
        self.assertEqual(ProgramState.CRASHED, state)

    def test_join(self):
        config = ProgramConfig.create(command="echo Test")
        program = Program("test_join", config, self.context)
        program.start()
        state = program.join()
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_interrupt(self):
        config = ProgramConfig.create(command="sleep 10")
        program = Program("test_interrupt", config, self.context)
        program.start()
        program.interrupt()
        state = program.join()
        self.assertEqual(ProgramState.STOPPED, state)

    def test_terminate(self):
        config = ProgramConfig.create(command="sleep 10")
        program = Program("test_terminate", config, self.context)
        program.start()
        program.terminate()
        state = program.join()
        self.assertEqual(ProgramState.STOPPED, state)

    def test_join_wait(self):
        config = ProgramConfig.create(command="echo test", startup_delay=0.1)
        program = Program("test_join_wait", config, self.context)
        state = program.start()
        self.assertEqual(ProgramState.WAITING, state)
        state = program.join_wait()
        self.assertEqual(ProgramState.SUCCEEDED, state)

    def test_cancel(self):
        config = ProgramConfig.create(command="echo test", startup_delay=1)
        program = Program("test_cancel", config, self.context)
        state = program.start()
        self.assertEqual(ProgramState.WAITING, state)
        state = program.interrupt()
        state = program.join_wait()
        self.assertEqual(ProgramState.CANCELED, state)
