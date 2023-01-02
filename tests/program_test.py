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
    ProgramStates,
)


class TestProgramObserver(LoggingProgramObserver):
    def __init__(self, logger: Logger) -> None:
        self.logger = logger


class ProgramTest(unittest.TestCase):
    logger: Logger

    @classmethod
    def setUpClass(cls) -> None:
        handler = StreamHandler()
        formatter = Formatter(
            "%(asctime)s %(levelname)-5.5s %(module)s %(program)s %(threadName)s: %(message)s"
        )
        handler.setFormatter(formatter)
        basicConfig(level=DEBUG, handlers=[handler])
        ProgramTest.logger = getLogger(__name__)

    def setUp(self):
        self.context = ExecutionContext(
            observer=TestProgramObserver(ProgramTest.logger)
        )

    def test_start(self):
        config = ProgramConfig.create(command='echo "Test"')
        program = Program("test_start", config, self.context)
        state = program.start(1)
        self.assertTrue(
            state in (ProgramStates.RUNNING, ProgramStates.SUCCEEDED), f"state: {state}"
        )
        state = program.join(10)
        self.assertEqual(ProgramStates.SUCCEEDED, state)
        self.assertTrue(program.has_ended())

    def test_start_fail(self):
        config = ProgramConfig.create(command='excho "Test"')
        program = Program("test_start_fail", config, self.context)
        state = program.start(1)
        self.assertEqual(ProgramStates.CRASHED, state)
        self.assertTrue(program.has_ended())

    def test_terminate(self):
        config = ProgramConfig.create(command="sleep 10")
        program = Program("test_terminate", config, self.context)
        program.start(1)
        program.terminate()
        program.join()
        self.assertTrue(program.has_ended())
