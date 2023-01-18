import yaml
import marshmallow_dataclass

from fnmatch import fnmatch
from io import TextIOBase
from typing import Dict, Set, List, Any, Mapping, Tuple, cast, Optional
from logging import Logger, Filter, LogRecord, getLogger, INFO
from pluggy import HookimplMarker  # type: ignore

from yaml.error import YAMLError
from dataclasses import dataclass, fields
from marshmallow.exceptions import MarshmallowError, ValidationError
from abc import ABC

ENCAB = "encab"
LOG_SANITIZER = "log_sanitizer"

mylogger = getLogger(LOG_SANITIZER)


class ConfigError(ValueError):
    pass


@dataclass
class LogSanitizerSettings(object):
    """
    the log sanitizer settings

    eample:

    .. code-block:: yaml

        encab:
            debug: true
            halt_on_exit: False
        extensions:
            log_sanitizer:
                enabled: true
                settings:
                    override: false
                    patterns:
                        - "*MAGIC*"

    This class contains the extensions/log_sanitizer/settings content.
    """

    patterns: Optional[List[str]]
    """set sensitive environmen variable name patterns whose values will be masked.
       UNIX file pattern rules are used (see https://docs.python.org/3/library/fnmatch.html#module-fnmatch)       
    
       example:
       
        ``*MAGIC*`` -- all variable names containing the string MAGIC 
    """

    override: Optional[bool]
    """if True, builtin patterns are overriden """

    def __post_init__(self):
        self.patterns = self.patterns or list()

        self.override = False if self.override is None else self.override

    @staticmethod
    def load(settings: Dict[str, Any]) -> "LogSanitizerSettings":
        try:
            ConfigSchema = marshmallow_dataclass.class_schema(LogSanitizerSettings)
            return ConfigSchema().load(settings)  # type: ignore
        except ValidationError as e:
            msg = e.args[0]
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"\n\n{LOG_SANITIZER}:\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(e.args)


class SanitizingFilter(Filter):
    def __init__(self, sensitive_strings: Set[str]) -> None:
        super().__init__()
        self.sensitive_strings = sensitive_strings

    def sanitize(self, value: Any) -> Any:
        for s in self.sensitive_strings:
            if isinstance(value, int) or isinstance(value, float):
                value = -1 if s == str(value) else value
            else:
                value = str(value).replace(s, "*" * len(s))
        return value

    def sanitize_all(self, args: Tuple[Any]):
        return tuple([self.sanitize(arg) for arg in args])

    def filter(self, record):
        record.msg = self.sanitize(record.msg)
        record.args = self.sanitize_all(cast(Tuple[Any], record.args))
        return True


extension_impl = HookimplMarker(ENCAB)


class LogSanitizerExtension(object):
    PATTERNS = ["*KEY*", "*SECRET*", "*PASSWORD", "*PWD*"]

    def __init__(self) -> None:
        self.sensitive_strings: Set[str] = set()
        self.settings = LogSanitizerSettings(patterns=self.PATTERNS, override=False)
        self.enabled = True

    @extension_impl
    def validate_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name == LOG_SANITIZER:
            LogSanitizerSettings.load(settings)
            mylogger.info("settings are valid.", extra={"program": ENCAB})

    @extension_impl
    def configure_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name != LOG_SANITIZER:
            return

        if not enabled:
            self.enabled = False
            return

        self.settings = LogSanitizerSettings.load(settings)

        if not self.settings.override:
            patterns = cast(List[str], self.settings.patterns)
            self.settings.patterns = [*patterns, *self.PATTERNS]

    def is_sensitive(self, name: str) -> bool:
        patterns = cast(List[str], self.settings.patterns)
        for pattern in patterns:
            if fnmatch(name.upper(), pattern.upper()):
                return True
        return False

    @extension_impl
    def extend_environment(self, program_name: str, environment: Dict[str, str]):
        if not self.enabled:
            return

        for name, value in environment.items():
            if self.is_sensitive(name):
                self.sensitive_strings.add(value)

    @extension_impl
    def update_logger(self, program_name: str, logger: Logger):
        if program_name == ENCAB:
            if self.enabled:
                patterns = str(self.settings.patterns)
                mylogger.debug(
                    "patterns: %s",
                    patterns,
                    extra={"program": program_name},
                )
            else:
                mylogger.info(
                    "log_sanitizer is disabled", extra={"program": program_name}
                )

        if not self.enabled:
            return

        logger.addFilter(SanitizingFilter(self.sensitive_strings))
