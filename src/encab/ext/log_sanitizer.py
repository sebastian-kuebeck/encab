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
class LogSanitizerConfig(object):
    patterns: Optional[List[str]]
    """set sensitive environmen variable name patterns whose values will be masked.
       UNIX file pattern rules are used (see https://docs.python.org/3/library/fnmatch.html#module-fnmatch)       
    
       example:
       
       - *MAGIC*    # all variable names containing the string MAGIC 
    """

    override: Optional[bool]
    """if true, builtin patterns are overriden """

    def __post_init__(self):
        self.patterns = self.patterns or list()

        self.override = False if self.override is None else self.override

    @staticmethod
    def load(settings: Dict[str, Any]) -> "LogSanitizerConfig":
        try:
            ConfigSchema = marshmallow_dataclass.class_schema(LogSanitizerConfig)
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

class LogSanititerExtension(object):
    PATTERNS = ["*KEY*", "*SECRET*", "*PASSWORD", "*PWD*"]

    def __init__(self) -> None:
        self.sensitive_strings: Set[str] = set()
        self.config = LogSanitizerConfig(patterns=self.PATTERNS, override=False)
        self.enabled = True

    @extension_impl
    def configure_extension(self, name: str, enabled: bool, config: Dict[str, Any]):
        if name != LOG_SANITIZER:
            return

        if not enabled:
            self.enabled = False
            return

        self.config = LogSanitizerConfig.load(config)
        
        if not self.config.override:
            patterns = cast(List[str], self.config.patterns)
            self.config.patterns = [*patterns, *self.PATTERNS]

    def is_sensitive(self, name: str) -> bool:
        patterns = cast(List[str], self.config.patterns)
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
                patterns = str(self.config.patterns)
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
