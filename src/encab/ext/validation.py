import sys
import yaml
import marshmallow_dataclass

from re import match, Pattern, compile

from fnmatch import fnmatch
from io import TextIOBase
from typing import Dict, Set, List, Any, Mapping, Tuple, cast, Optional, Union
from logging import Logger, Filter, LogRecord, getLogger, INFO
from pluggy import HookimplMarker  # type: ignore

from yaml.error import YAMLError
from dataclasses import dataclass, fields
from marshmallow.exceptions import MarshmallowError, ValidationError
from abc import ABC

ENCAB = "encab"
VALIDATION = "validation"

mylogger = getLogger(VALIDATION)


class ConfigError(ValueError):
    pass


@dataclass
class Validation(object):

    required: Optional[bool]

    default: Union[str, int, float, None]

    min_length: Optional[int]

    max_length: Optional[int]

    min_value: Optional[float]

    max_value: Optional[float]

    regex: Optional[str]

    program: Optional[str]

    programs: Optional[List[str]]

    def __post_init__(self):
        self.required = True if self.required is None else self.required

        regex = self.regex
        if isinstance(regex, str):
            try:
                compile(regex)
            except ValueError as e:
                raise ConfigError(
                    f"Expected 'regex' to be a valid regex but was {regex}: {str(e)}"
                )

        min_length = self.min_length
        max_length = self.max_length

        if min_length and min_length < 0:
            raise ConfigError(f"Expected min_length >=0 but was {min_length}")

        if max_length and max_length < 0:
            raise ConfigError(f"Expected max_length >=0 but was {max_length}")

        if min_length and max_length and max_length < min_length:
            raise ConfigError(
                f"Expected max_length >= min_length was {max_length} < {min_length}"
            )

        if self.program and self.programs:
            raise ConfigError(f"Expected either 'program' or 'programs' but got both.")

        self.programs = [self.program] if self.program else (self.programs or list())

        min_value = self.min_value
        max_value = self.max_value

        if min_value and max_value and max_value < min_value:
            raise ConfigError(
                f"Expected max_value >= min_value was {max_value} < {min_value}"
            )


@dataclass
class ValidationSettings(object):
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
                    variables:
                        X:
                            required: true
                            default: 1
                            min_length: 1
                            max_length: 5
                            regex: /.*/
                        Y:
                            format: numeric


    This class contains the extensions/startup_script/settings content.
    """

    variables: Dict[str, Validation]

    def __post_init__(self):
        pass

    @staticmethod
    def load(settings: Dict[str, Any]) -> "ValidationSettings":
        try:
            ConfigSchema = marshmallow_dataclass.class_schema(ValidationSettings)
            return ConfigSchema().load(settings)  # type: ignore
        except ValidationError as e:
            msg = e.args[0]
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"\n\n{VALIDATION}:\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(e.args)


extension_impl = HookimplMarker(ENCAB)


class Validator(object):
    def __init__(self) -> None:
        self.settings = ValidationSettings(dict())
        self.validations: Dict[str, Validation] = dict()

    def update_settings(self, settings: ValidationSettings):
        variables = settings.variables or dict()
        self.validations.update(variables)

    def range(self, name: str, value: str, validation: Validation):
        min_value = validation.min_value
        max_value = validation.max_value

        if min_value or max_value:
            try:
                n = float(value)
            except:
                raise ConfigError(
                    f"Expected {name} to be float as "
                    f"min_value and/or max_value was given but was '{value}'"
                )

            if min_value and n < min_value:
                raise ConfigError(f"Expected {name} >= {min_value} but was {n}")

            if max_value and n > max_value:
                raise ConfigError(f"Expected {name} <= {max_value} but was {n}")

    def length(self, name: str, value: str, validation: Validation):
        min_length = validation.min_length
        max_length = validation.max_length

        if min_length and len(value) < min_length:
            raise ConfigError(
                f"Expected {name} length >= {min_length} but was {len(value)}"
            )

        if max_length and len(value) > max_length:
            raise ConfigError(
                f"Expected {name} length <= {max_length} but was {len(value)}"
            )

    def regex(self, name: str, value: str, validation: Validation):
        regex = validation.regex

        if regex and not match(regex, value):
            raise ConfigError(f"Expected {name} to match '{str(regex)}'")

    def var(self, program: str, name: str, value: str):
        validation: Optional[Validation] = self.validations.get(name)

        if not validation:
            return

        if validation.programs and program not in validation.programs:
            return

        mylogger.debug(
            "Validating variable %s for program %s",
            name,
            program,
            extra={"program": ENCAB},
        )

        self.range(name, value, validation)
        self.length(name, value, validation)
        self.regex(name, value, validation)

    def validate(self, program: str, vars: Dict[str, str]):
        vars_set: Set[str] = set()

        for name, value in vars.items():
            if value:
                vars_set.add(name)
                self.var(program, name, value)

        # mylogger.debug("Variables set so far: %s", str(vars_set), extra={"program": ENCAB})

        for name, validation in self.validations.items():
            if validation.programs and program not in validation.programs:
                continue

            if name in vars_set:
                continue

            if validation.default:
                mylogger.debug(
                    "Program %s: setting default %s = %s",
                    program,
                    name,
                    validation.default,
                    extra={"program": ENCAB},
                )
                vars[name] = str(validation.default)
                continue

            if validation.required:
                raise ConfigError(f"Missing required parameter {name}")


class ValidationExtension(object):
    def __init__(self) -> None:
        self.validator = Validator()
        self.enabled = True
        self.programs_updated: Set[str] = set()

    @extension_impl
    def validate_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name == VALIDATION:
            ValidationSettings.load(settings)
            mylogger.info("settings are valid.", extra={"program": ENCAB})

    @extension_impl
    def configure_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name != VALIDATION:
            return

        if not enabled:
            self.enabled = False
            return

        self.validator.update_settings(ValidationSettings.load(settings))

    @extension_impl
    def extend_environment(self, program_name: str, environment: Dict[str, str]):
        if not self.enabled:
            return

        if program_name == ENCAB:
            return

        if program_name in self.programs_updated:
            self.validator.validate(program_name, environment)
        else:
            self.programs_updated.add(program_name)
