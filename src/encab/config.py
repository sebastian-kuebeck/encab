import io
import os
import shlex
import yaml
import marshmallow_dataclass

from pwd import getpwnam
from yaml.error import YAMLError
from typing import Dict, Optional, Union, List, Any
from dataclasses import dataclass, fields
from marshmallow.exceptions import MarshmallowError, ValidationError
from logging import DEBUG, INFO
from abc import ABC


class ConfigError(ValueError):
    pass


@dataclass
class AbstractConfig(ABC):
    """
    Configuration base dataclass
    """

    @classmethod
    def create(cls, **args):
        """
        creates an instance and sets all missing optional fields to None

        :return: the data class
        :rtype: same as cls
        """
        config_class = dataclass(cls, kw_only=True)
        config_fields = fields(config_class)
        all_args = dict(args)
        for field in config_fields:
            name = field.name
            if name not in args:
                all_args[name] = None

        return config_class(**all_args)


@dataclass
class AbstractProgramConfig(AbstractConfig):
    """
    Common config for encab and programs section
    """

    environment: Optional[Dict[str, str]]
    """set additional environmment variables"""

    debug: Optional[bool]
    """if True, encab logs debug information. Default: False"""

    loglevel: Optional[Union[str, int]]
    """the log level. One of "CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG"."""

    umask: Optional[Union[str, int]]
    """the umask, either as octal string (e.g. "077") or integer"""

    user: Optional[Union[str, int]]
    """the user id or user name"""

    shell: Optional[bool]
    """if true: execute programs in the shell. Default: false"""

    logFormat: Optional[str]
    """
    Custom log format (see `logrecord-attributes-link`_). 
    The attribute "program" contains the ptogram name. 
    
    see: 
    
    Default: %(levelname)-5.5s %(program)s: %(message)s 
    
    .. _logrecord-attributes-link: https://docs.python.org/3/library/logging.html#logrecord-attributes
    """

    join_time: Optional[float]
    """ 
    The join time is the time in seconds encab waits for a program to start/shutdown before 
    it continues with the next. Default: 1 seconds
    """

    def _set_umask(self):
        umask = self.umask

        if umask:
            if isinstance(umask, int):
                self.umask = int(umask)
            else:
                try:
                    self.umask = int(umask, 8)
                except ValueError:
                    raise ConfigError(f"Invalid octal string for umask: {umask}")
        else:
            self.umask = -1

    def _set_user(self):
        user = self.user

        if user:
            if isinstance(user, int) or user.isnumeric():
                self.user = int(user)
            else:
                try:
                    self.user = getpwnam(user).pw_uid
                except KeyError:
                    raise ConfigError(f"Unknown user {user}")

            if user != os.getuid() and os.getuid() != 0:
                raise ConfigError(
                    f"Encab has to run as root to run it or programs as different user"
                )

    def _set_log_level(self):
        levels = ["CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG"]

        level = self.loglevel

        if level and level not in levels:
            levels_printed = ", ".join(levels)
            raise ConfigError(
                f"Unsupported log level {level}. Supported levels are: {levels_printed}"
            )

        self.loglevel = DEBUG if self.debug else (level or INFO)

    def __post_init__(self):
        """
        validates fields and sets default values

        :raises ConfigError: if fields have invalid values
        """

        self._unsetFields = [
            f.name for f in fields(self) if getattr(self, f.name) is None
        ]
        """name of fields which were not set in this configuration"""

        self.environment = self.environment or dict()

        self._set_log_level()
        self._set_user()
        self._set_umask()

        self.shell = self.shell or False
        self.join_time = self.join_time or 1.0

    def extend(self, other: "AbstractProgramConfig"):
        """
        Extends configration with values from a given configuration

        If a field of the current configuration was not set, it is set by the field
        value of the given configuration.

        :param other: the given configuration
        :type other: AbstractProgramConfig
        """
        for name in self._unsetFields:
            if hasattr(other, name):
                v = getattr(other, name)
                if v is not None:
                    setattr(self, name, v)


@dataclass
class EncabConfig(AbstractProgramConfig):
    """
    reprensents the encab base configuration

    contains all static settings to start a program
    """

    halt_on_exit: Optional[bool]
    """halt on exit: if True, encab is halted after the main program ends. Default: False"""

    def __post_init__(self):
        super().__post_init__()

        if self.halt_on_exit is None:
            self.halt_on_exit = False


@dataclass
class ProgramConfig(AbstractProgramConfig):
    """
    reprensents a program configuraion

    contains all static settings to start a program
    """

    command: Union[str, List[str]]
    """the command to be execution in POSIX style
        example:
            echo "Test"
    """

    startup_delay: Optional[float]
    """The startup delay for this program in seconds. Default: 0 seconds"""

    def __post_init__(self):
        """
        validates fields and sets default values

        :raises ConfigError: if fields have invalid values
        """
        super().__post_init__()

        command = self.command
        self.command = shlex.split(command) if isinstance(command, str) else command

        self.startup_delay = self.startup_delay or 0


@dataclass
class Config(AbstractConfig):
    """
    represents a complete Encab configuration
    """

    encab: Optional[EncabConfig]
    """the basic encab configuraion"""

    plugins: Optional[Dict[str, Any]]
    """a dictionary with plugin manes and their configuration"""

    programs: Optional[Dict[str, ProgramConfig]]
    """a dictionary with program names and their program configuration"""

    @staticmethod
    def load(stream: io.TextIOBase) -> "Config":
        """
        loads a configuration from a Yaml stream

        :param stream: the Yaml stream
        :type stream: io.TextIOBase
        :raises ConfigError: if the Yaml file is invalid or doesn't match configuration requirements
        :return: the configuration
        :rtype: Config
        """
        try:
            ConfigSchema = marshmallow_dataclass.class_schema(Config)
            return ConfigSchema().load(yaml.safe_load(stream))
        except YAMLError as e:
            raise ConfigError(f"YAML error(s) {str(e)}")
        except ValidationError as e:
            msg = e.args[0]
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"\n\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(e.args)
