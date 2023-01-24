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
    """
    Configuration error
    """

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
        config_class = dataclass(cls, kw_only=True)  # type: ignore
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
                    raise ConfigError(
                        f"Expected octal string for umask but got: {umask}"
                    )
        else:
            self.umask = -1

    def set_user(self):
        """
        sets the user that runs the program

        steps:
        - checks wether a user is set.
        - determines the UID if the user is given as name.
        - checks if encab is run as root if a program is set to run with a different user.

        :raises ConfigError: if the user is unknown or encab is not run as root when needed
        """
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
        self._set_umask()

        self.join_time = self.join_time or 1.0

    def was_unset(self, field_name: str) -> bool:
        """
        returns true if a field was initially unset

        :param field_name: the field name
        :type field_name: str
        :return: True: the field was initially unset, False: the field was set
        :rtype: bool
        """
        return field_name in self._unsetFields

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

    logformat: Optional[str]
    """
    Custom log format (see logrecord-attributes_). 
    The attribute "program" contains the ptogram name. 
    
    .. _logrecord-attributes: https://docs.python.org/3/library/logging.html#logrecord-attributes
    
    Default: ``%(levelname)-5.5s %(program)s: %(message)s``
    
    
    """

    dry_run: Optional[bool]
    """True: the configuration is checked but no program is started. Default: False"""

    def _set_log_format(self):
        default_format = "%(levelname)-5.5s %(program)s: %(message)s"
        debug_format = "%(asctime)s %(levelname)-5.5s %(module)s %(program)s %(threadName)s: %(message)s"

        if self.logformat:
            return

        if self.debug:
            self.logformat = debug_format
        else:
            self.logformat = default_format

    def __post_init__(self):
        super().__post_init__()

        self.dry_run = None if self.dry_run is None else self.dry_run

        if self.halt_on_exit is None:
            self.halt_on_exit = False

        self._set_log_format()


@dataclass
class ProgramConfig(AbstractProgramConfig):
    """
    reprensents a program configuraion

    contains all static settings to start a program
    """

    command: Union[str, List[str], None]
    """the command to be execution as list in POSIX style
        examples:
        
        .. code-block:: yaml
        
            program:
                command:
                    echo "Test"
       
        .. code-block:: yaml
        
            program:
                comand:     
                    - echo 
                    - Test
    """

    sh: Union[str, List[str], None]
    """the shell script as string or list
    
        examples:
        
            .. code-block:: yaml
        
                program:
                    sh:
                        echo "Test"
                    
            .. code-block:: yaml
       
                program:
                    sh:     
                        - echo "Test1" 
                        - echo "Test2"
    """
    startup_delay: Optional[float]
    """The startup delay for this program in seconds. Default: 0 seconds"""

    def __post_init__(self):
        """
        validates fields and sets default values

        :raises ConfigError: if fields have invalid values
        """
        super().__post_init__()

        sh = self.sh
        command = self.command

        if sh and command:
            raise ConfigError(
                f"Please specify either sh or command attribute for programs"
            )

        if command:
            self.command = shlex.split(command) if isinstance(command, str) else command

        if sh:
            self.sh = sh if isinstance(sh, str) else "; ".join(sh)

        self.startup_delay = self.startup_delay or 0


@dataclass
class ExtensionConfig(AbstractConfig):
    """
    represents an extension configuration
    """

    enabled: Optional[bool]
    """True: The extension is enabled"""

    '''
    Necessary ?
    
    source: Optional[str]
    """Source path of extension"""

    module: Optional[str]
    """Module name of extension"""
    '''

    settings: Optional[Dict[str, Any]]

    def __post_init__(self):
        self.enabled = True if self.enabled is None else self.enabled


@dataclass
class Config(AbstractConfig):
    """
    represents a complete Encab configuration
    """

    encab: Optional[EncabConfig]
    """the basic encab configuraion"""

    extensions: Optional[Dict[str, ExtensionConfig]]
    """a dictionary with extension manes and their configuration"""

    programs: Optional[Dict[str, ProgramConfig]]
    """a dictionary with program names and their program configuration"""

    def __post_init__(self):
        if not self.encab:
            self.encab = EncabConfig.create()

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
            return ConfigSchema().load(yaml.safe_load(stream))  # type: ignore
        except YAMLError as e:
            raise ConfigError(f"YAML error(s) {str(e)}")
        except ValidationError as e:
            msg = e.args[0]
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"\n\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(e.args)
