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
STARTUP_SCRIPT = "startup_script"

mylogger = getLogger(STARTUP_SCRIPT)


class ConfigError(ValueError):
    pass


@dataclass
class StartupScriptSettings(object):
    """
    the startup script settings

    eample:

    .. code-block:: yaml

        encab:
            debug: true
            halt_on_exit: False
        extensions:
            validation:
                enabled: true
                settings:
                    varables:
                        X:
                            required: true
                            default: 1
                            length: "1:5"
                            match: ".*"
                        Y:
                            format: numeric


    This class contains the extensions/startup_script/settings content.
    """

    loadenv: Optional[List[str]]
    sh: Optional[List[str]]

    def __post_init__(self):
        pass

    @staticmethod
    def load(settings: Dict[str, Any]) -> "StartupScriptSettings":
        try:
            ConfigSchema = marshmallow_dataclass.class_schema(StartupScriptSettings)
            return ConfigSchema().load(settings)  # type: ignore
        except ValidationError as e:
            msg = e.args[0]
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"\n\n{STARTUP_SCRIPT}:\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(e.args)
