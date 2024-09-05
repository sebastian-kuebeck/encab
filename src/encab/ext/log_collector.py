import yaml
import marshmallow_dataclass

from typing import Dict, List, Any, Optional, Union
from logging import Logger, getLogger, INFO, getLevelName
from pluggy import HookimplMarker  # type: ignore

from dataclasses import dataclass
from marshmallow.exceptions import MarshmallowError, ValidationError
from io import TextIOBase

import re
from datetime import datetime

import os
import stat
from threading import Thread, Event

ENCAB = "encab"
LOG_COLLECTOR = "log_collector"

mylogger = getLogger(LOG_COLLECTOR)


class ConfigError(ValueError):
    pass


@dataclass
class SourceConfig(object):

    path: Optional[str]
    """The path of the log file"""

    path_pattern: Optional[str]
    """
    The path pattern of the log file
    
    ``%(<name>)e`` inserts the value of the environment variable with name <name>
    
    ``%(<dateformat>)d`` inserts the current time with <dateformat> as python date format, 
    
    see https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    
    ``%`` must be masked with ``%%``
    
    examples:
    
    - ``%(HOME)e/path`` -> ``/home/user/path``
    - ``error-%(%y%m%d)d.log`` -> ``error-20230103.log``
    - ``a%%b.log`` -> ``a%b.log``
    """

    offset: Optional[int]
    """The initial read offset, defaults to 0
    
       -1     : Start at the beginning of the file
        0     : Start at the end of the file
        n > 0 : Start n characters before the end of the file
    """

    level: Union[str, int, None]
    """The log level"""

    poll_interval: Optional[float]
    """The poll interval in seconds"""

    def _set_log_level(self):
        """
        checks the log level and turns it into an int if necessary

        :raises ConfigError: if an unspecified log level is given
        """
        levels = ["CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG"]

        level = self.level

        if level and isinstance(level, str) and level not in levels:
            levels_printed = ", ".join(levels)
            raise ConfigError(
                f"Unsupported log level {level}. Supported levels are: {levels_printed}"
            )

        level = level or INFO
        self.level = level if isinstance(level, int) else getLevelName(level)

    def __post_init__(self):
        if not self.path and not self.path_pattern:
            raise ConfigError(
                "Either path ot path_pattern must be set in log_collector source"
            )

        if self.path and self.path_pattern:
            raise ConfigError(
                "Either path ot path_pattern must be set but not both in log_collector source"
            )

        self._set_log_level()


@dataclass
class LogCollectorSettings(object):
    """
    the log collector settings

    eample:

    .. code-block:: yaml

        encab:
            debug: true
            halt_on_exit: False
        extensions:
            log_collector:
                enabled: true
                settings:
                    sources:
                        error_log:
                            file: ./error.log

    This class contains the extensions/log_collector/settings content.
    """

    sources: Dict[str, SourceConfig]

    def __post_init__(self):
        pass

    @staticmethod
    def load(settings: Dict[str, Any]) -> "LogCollectorSettings":
        try:
            ConfigSchema = marshmallow_dataclass.class_schema(LogCollectorSettings)
            return ConfigSchema().load(settings)  # type: ignore
        except ValidationError as e:
            msg = e.args[0]
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"\n\n{LOG_COLLECTOR}:\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(e.args)


class PathPattern(object):
    FORMAT = re.compile(r"((%%|[^%])*)|(%\([^\)]*\)[ed])")

    def __init__(self, pattern: str) -> None:
        self.tokens = self.FORMAT.findall(pattern)

    def replace(self, pattern: str, time: datetime, environment: Dict[str, str]) -> str:
        suffix = pattern[-1]
        pattern = pattern[2:-2]

        if suffix == "e":
            name = pattern
            if name not in environment:
                return ""

            return environment[name]
        else:
            date_format = pattern
            try:
                return time.strftime(date_format)
            except ValueError as e:
                raise ConfigError(
                    f"Malformed date format '{date_format}' in log_collector source: {str(e)}"
                )

    def format(self, time: datetime, environment: Dict[str, str]) -> str:
        result = list()
        for token in self.tokens:
            if token[0]:
                result.append(token[0].replace("%%", "%"))
            elif token[2]:
                result.append(self.replace(token[2], time, environment))

        return "".join(result)


class LogPath(object):
    def __init__(
        self, path_or_pattern: str, environment: Dict[str, str], fixed: bool
    ) -> None:
        self._fixed_path = path_or_pattern if fixed else None
        self._path_pattern = None if fixed else PathPattern(path_or_pattern)
        self._environment = environment

    @staticmethod
    def fixed(path: str) -> "LogPath":
        return LogPath(path, dict(), True)

    @staticmethod
    def variable(path_pattern: str, environment: Dict[str, str]) -> "LogPath":
        return LogPath(path_pattern, environment, False)

    def current(self, time: datetime):
        if self._fixed_path:
            return self._fixed_path
        else:
            time = time or datetime.now()
            assert self._path_pattern
            return self._path_pattern.format(time, self._environment)

    def is_fixed(self):
        return self._fixed_path is not None


class Stopped(Exception):
    pass


class LogCollector(object):
    def __init__(
        self,
        name: str,
        path: LogPath,
        logger: Logger,
        level: int = INFO,
        offset: int = 0,
        poll_interval: float = 0.5,
    ) -> None:
        self.name = name
        self.path = path
        self.logger = logger
        self.level = level
        self.extra = {"program": name}
        self.offset = offset
        self.poll_interval = poll_interval

        self._thread = None
        self._started = Event()
        self._stop = Event()
        self._stopped = Event()
        self._current_time: Optional[datetime] = None
        self._fp: Optional[TextIOBase] = None
        self._file_existed_at_start = False

    def __now(self) -> datetime:
        return self._current_time or datetime.now()

    def current_path(self) -> str:
        return self.path.current(self.__now())

    def __st_mode(self) -> int:
        return os.stat(self.current_path()).st_mode

    def file_exists(self):
        try:
            st_mode = self.__st_mode()
            return stat.S_ISREG(st_mode) or stat.S_ISFIFO(st_mode)
        except FileNotFoundError:
            return False

    def is_regular_file(self):
        try:
            st_mode = self.__st_mode()
            return stat.S_ISREG(st_mode)
        except FileNotFoundError:
            return False

    def check_stopped(self):
        if self._stop.is_set():
            raise Stopped()

    def get_fp(self):
        if self._fp:
            return self._fp
        else:
            raise Stopped()

    def clear_fp(self):
        self._fp = None

    def log_lines(self):
        for line in self.get_fp():
            line = line.rstrip("\r\n\t ")
            self.logger.log(self.level, line, extra=self.extra)

    def open(self, path: str) -> TextIOBase:
        fp = open(path, "r")
        self._fp = fp
        return fp

    def fast_forward(self):
        if self.offset == -1 or not self._file_existed_at_start:
            return

        fp = self.get_fp()
        fp.seek(0, 2)
        pos = fp.tell()
        pos = max(pos - self.offset, 0)

        if pos > 0:
            fp.seek(pos)

    def poll_data(self, path: str):
        fp = self.get_fp()
        pos = fp.tell()
        self.logger.debug(
            f"Waiting for new data in file {path}...",
            extra=self.extra,
        )
        self._stop.wait(self.poll_interval)
        self.check_stopped()
        fp.seek(pos)

    def collect_fifo(self):
        path = self.current_path()
        with self.open(path):
            self.log_lines()

    def collect_file(self):
        path = self.current_path()
        with self.open(path):
            self.fast_forward()
            while True:
                self.log_lines()
                self.poll_data(path)

    def same_log_file(self, path: str) -> bool:
        current_path = self.current_path()
        same_file = path == current_path

        if not same_file:
            mylogger.debug("Log path changed from %s to %s", path, current_path)

        return same_file

    def collect_rolling_files(self):
        is_first_file = True

        while True:
            path = self.current_path()
            with self.open(path):
                if is_first_file:
                    self.fast_forward()
                    is_first_file = False

                while True:
                    self.log_lines()
                    self.check_stopped()

                    if not self.same_log_file(path):
                        break

                    self.poll_data(path)

    def poll_file(self):
        while not self.file_exists():
            self.check_stopped()
            self.logger.debug(
                "Waiting for file %s ...", self.current_path(), extra=self.extra
            )
            self._stop.wait(self.poll_interval)

    def _run(self):
        try:
            self._file_existed_at_start = self.file_exists()
            self._started.set()

            while True:
                try:
                    self.clear_fp()
                    self.poll_file()
                    self.check_stopped()
                    if not self.file_exists():
                        raise Stopped()

                    if not self.is_regular_file():
                        self.collect_fifo()
                    else:
                        if self.path.is_fixed():
                            self.collect_file()
                        else:
                            self.collect_rolling_files()

                except FileNotFoundError:
                    pass
                except BrokenPipeError:
                    pass

        except Stopped:
            pass
        except Exception as e:
            self.logger.exception(
                "Reading source %s failed: %s", self.name, str(e), extra=self.extra
            )
        finally:
            self.clear_fp()
            self._stopped.set()

    def start(self, wait_time: float = 0.1, current_time: Optional[datetime] = None):
        self._current_time = current_time
        thread = Thread(target=lambda: self._run(), name=self.name)
        thread.daemon = True
        self.thread = thread
        thread.start()
        self._started.wait(wait_time)
        return self

    def set_current_time(self, current_time: datetime):
        self._current_time = current_time

    def stop(self, wait_time: float = 1.0):
        self._stop.set()
        if self._fp:
            try:
                self._fp.close()
            except IOError:
                pass
            self._fp = None
        self._stopped.wait(wait_time)


extension_impl = HookimplMarker(ENCAB)


class LogCollectorExtension(object):
    def __init__(self) -> None:
        self.settings: Optional[LogCollectorSettings] = None
        self.enabled = True
        self.collectors: List[LogCollector] = list()

    def add_collectors(self, environment: Dict[str, str]):
        if not self.settings:
            return

        for name, source in self.settings.sources.items():
            path = None
            if source.path:
                path = LogPath.fixed(source.path)
            if source.path_pattern:
                path = LogPath.variable(source.path_pattern, environment)

            assert path
            level = source.level
            assert isinstance(level, int)
            collector = LogCollector(
                name=name,
                path=path,
                logger=mylogger,
                level=level,
                offset=source.offset or -1,
                poll_interval=source.poll_interval or 1,
            )
            self.collectors.append(collector)

    def start_collectors(self):
        for collector in self.collectors:
            collector.start()

    def stop_collectors(self):
        for collector in self.collectors:
            collector.stop()

    @extension_impl
    def validate_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name == LOG_COLLECTOR:
            self.settings = LogCollectorSettings.load(settings)
            mylogger.info("settings are valid.", extra={"program": ENCAB})

    @extension_impl
    def configure_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name != LOG_COLLECTOR:
            return

        if not enabled:
            self.enabled = False
            return

        self.settings = LogCollectorSettings.load(settings)

    @extension_impl
    def extend_environment(self, program_name: str, environment: Dict[str, str]):
        if not self.enabled:
            return

        if not self.collectors:
            self.add_collectors(environment)
            self.start_collectors()

    @extension_impl
    def programs_ended(self):
        if self.enabled:
            self.stop_collectors()
