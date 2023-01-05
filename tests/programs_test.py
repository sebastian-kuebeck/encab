import io
import unittest

from typing import List, Dict, Tuple, Optional

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
from encab.config import ProgramConfig, EncabConfig
from encab.program import LoggingProgramObserver, ProgramObserver, ExecutionContext
from encab.programs import Programs
from time import sleep
from queue import Queue


class TestProgramObserver(LoggingProgramObserver):
    def __init__(
        self,
        name: str,
        logger: Logger,
        extra: Dict[str, str],
        parent: Optional["TestProgramObserver"] = None,
    ) -> None:
        super().__init__(name, logger, extra)
        self.parent = parent
        self.observer = self.parent or self

        self._executions: List[Tuple[str, List[str], Dict[str, str]]] = []
        self._exits: Queue = Queue()

    def spawn(
        self, name: str, logger: Logger, extra: Dict[str, str]
    ) -> ProgramObserver:
        return TestProgramObserver(name, logger, extra, self)

    def get_executions(self):
        return self._executions

    def get_exits(self, count: int = 2) -> List[Tuple[str, int]]:
        exits: List[Tuple[str, int]] = list()
        for count in range(count):
            exits.append(self.observer._exits.get(timeout=0.5))
        return sorted(exits, key=lambda e: e[0], reverse=True)

    def add_execution(self, entry: Tuple[str, List[str], Dict[str, str]]):
        self.observer._executions.append(entry)

    def add_exit(self, entry: Tuple[str, int]):
        self.observer._exits.put(entry)

    def on_execution(self, cmd: List[str], env: Dict[str, str], config: ProgramConfig):
        super().on_execution(cmd, env, config)
        self.add_execution((self.name, cmd, env))

    def on_exit(self, rc: int):
        super().on_exit(rc)
        self.add_exit((self.name, rc))

    def on_stopped(self):
        super().on_stopped()
        self.add_exit((self.name, 15))

    def on_crash(self, cmd: List[str], e: BaseException):
        super().on_crash(cmd, e)
        self.add_exit((self.name, -1))


class ProgramsTest(unittest.TestCase):
    logger: Logger

    @classmethod
    def setUpClass(cls) -> None:
        handler = StreamHandler()
        formatter = Formatter(
            "%(asctime)s %(levelname)-5.5s %(program)s %(threadName)s: %(message)s"
        )
        handler.setFormatter(formatter)

        basicConfig(level=DEBUG, handlers=[handler])
        ProgramsTest.logger = getLogger(__name__)

    def setUp(self):
        self.observer = TestProgramObserver(
            "encab", ProgramsTest.logger, {"program": "encab"}
        )
        self.context = ExecutionContext({"X": "1"}, observer=self.observer)
        self.encab_config = EncabConfig.create(debug=False)

    def test_run(self):
        config = {
            "helper": ProgramConfig.create(command="sleep 10", environment={"Y": "2"}),
            "main": ProgramConfig.create(
                command='echo "Test"',
                environment={"Z": "3"},
            ),
        }

        programs = Programs(config, self.context, [], self.encab_config)
        programs.run()

        self.assertEqual(
            [
                ("helper", ["sleep", "10"], {"X": "1", "Y": "2"}),
                ("main", ["echo", "Test"], {"X": "1", "Z": "3"}),
            ],
            self.observer.get_executions(),
        )

        self.assertEqual([("main", 0), ("helper", 15)], self.observer.get_exits(2))

    def test_run_with_crashing_main(self):
        config = {
            "helper": ProgramConfig.create(command="sleep 10"),
            "main": ProgramConfig.create(command='echxo "Test"'),
        }

        programs = Programs(config, self.context, [], self.encab_config)
        programs.run()

        self.assertEqual(
            [
                ("helper", ["sleep", "10"], {"X": "1"}),
                ("main", ["echxo", "Test"], {"X": "1"}),
            ],
            self.observer.get_executions(),
        )

        self.assertEqual([("main", -1), ("helper", 15)], self.observer.get_exits(2))

    def test_run_override_main(self):
        config = {
            "helper": ProgramConfig.create(command="sleep 10"),
            "main": ProgramConfig.create(sh='echo "Main"'),
        }

        programs = Programs(
            config, self.context, ["echo", "Custom Main"], self.encab_config
        )
        programs.run()

        self.assertEqual(
            [
                ("helper", ["sleep", "10"], {"X": "1"}),
                ("main", ["echo", "Custom Main"], {"X": "1"}),
            ],
            self.observer.get_executions(),
        )
        self.assertEqual([("main", 0), ("helper", 15)], self.observer.get_exits(2))

    def test_interrupt(self):
        config = {
            "helper": ProgramConfig.create(command="sleep 10"),
            "main": ProgramConfig.create(command="sleep 10"),
        }

        programs = Programs(config, self.context, [], self.encab_config)
        programs.start()
        programs.terminate()
        self.assertEqual([("main", 15), ("helper", 15)], self.observer.get_exits(2))
