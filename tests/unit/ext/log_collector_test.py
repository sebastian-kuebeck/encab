from typing import Dict, Optional, List
from logging import Logger, DEBUG, INFO, Handler, LogRecord

from encab.ext.log_collector import LogCollector, PathPattern, LogPath

import os
import tempfile
import time
from datetime import datetime

import unittest


class TestLogHandler(Handler):
    def __init__(self, level: int = 0) -> None:
        super().__init__(level)
        self.records: List[LogRecord] = list()

    def emit(self, record):
        assert isinstance(record, LogRecord)
        self.records.append(record)

    def clear(self):
        self.records.clear()


class PathPathTest(unittest.TestCase):
    def assert_match(
        self,
        expected: str,
        pattern: str,
        env: Optional[Dict[str, str]] = None,
        date: Optional[datetime] = None,
    ):
        env = env or dict()
        date = date or datetime.strptime("20230201160000", "%Y%m%d%H%M%S")
        path = PathPattern(pattern).format(date, env)
        self.assertEqual(expected, path)

    def test_plain_path_pattern(self):
        self.assert_match("apath", "apath")

    def test_mask_percent_pattern(self):
        self.assert_match("file%path", "file%%path")

    def test_replace_environment(self):
        self.assert_match(
            "home/user/file.log", "%(HOME)e/file.log", env={"HOME": "home/user"}
        )

    def test_replace_datetime(self):
        self.assert_match("error-20230201.log", "error-%(%Y%m%d)d.log")


class LogCollectorTest(unittest.TestCase):
    handler: TestLogHandler
    logger: Logger
    loglevel: int

    @classmethod
    def setUpClass(cls) -> None:
        cls.loglevel = DEBUG
        cls.handler = TestLogHandler()
        logger = Logger("test", cls.loglevel)
        logger.addHandler(cls.handler)
        cls.logger = logger

    def setUp(self) -> None:
        super().setUp()
        self.handler.clear()

    def write_lines(self, path: str):
        with open(path, "w") as fp:
            for i in range(5):
                fp.write(f"line {i} \n")
                fp.flush()
        time.sleep(0.2)

    def test_fifo(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "encabtestfifo")
        os.mkfifo(path)

        source = LogCollector(
            "test_source", LogPath.fixed(path), self.logger, poll_interval=0.1
        )
        source.start()

        self.write_lines(path)

        source.stop()

        messages = [rec.msg for rec in self.handler.records]

        self.assertEqual([f"line {i}" for i in range(5)], messages)

    def recorded_messages(self) -> List[str]:
        return [rec.msg for rec in self.handler.records if rec.levelno == INFO]

    def test_source_file_fixed_path(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "encabtestfile")

        source = LogCollector(
            "test_source", LogPath.fixed(path), self.logger, poll_interval=0.1
        )
        source.start()

        self.write_lines(path)

        source.stop()

        self.assertEqual([f"line {i}" for i in range(5)], self.recorded_messages())

    def test_source_file_variable_path(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "encabtestfile-20230201.log")
        path_pattern = os.path.join(tmpdir, "encabtestfile-%(%Y%m%d)d.log")

        self.handler.clear()

        source = LogCollector(
            "test_source",
            LogPath.variable(path_pattern, dict()),
            self.logger,
            poll_interval=0.1,
        )
        date = datetime.strptime("20230201160000", "%Y%m%d%H%M%S")
        source.start(0.1, date)

        self.assertEqual(path, source.current_path())
        self.assertFalse(source.file_exists())

        self.write_lines(path)

        messages = self.recorded_messages()
        self.assertEqual(5, len(messages))
        self.assertEqual([f"line {i}" for i in range(5)], self.recorded_messages())

        date = datetime.strptime("20230202160000", "%Y%m%d%H%M%S")
        source.set_current_time(date)
        path = os.path.join(tmpdir, "encabtestfile-20230202.log")
        self.assertEqual(path, source.current_path())

        self.write_lines(path)

        self.assertTrue(source.file_exists())

        source.stop()

        messages = [rec.msg for rec in self.handler.records if rec.levelno == INFO]
        self.assertEqual(10, len(messages))
        self.assertEqual([f"line {i % 5}" for i in range(10)], self.recorded_messages())
