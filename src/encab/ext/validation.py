import re
import yaml
import marshmallow_dataclass

from re import match, compile

from abc import ABC, abstractmethod
from typing import Dict, Set, List, Any, Optional, Union
from logging import getLogger
from pluggy import HookimplMarker  # type: ignore

from yaml.error import YAMLError
from dataclasses import dataclass
from marshmallow.exceptions import MarshmallowError, ValidationError

ENCAB = "encab"
VALIDATION = "validation"

mylogger = getLogger(VALIDATION)


class ConfigError(ValueError):
    pass


@dataclass
class Validation(object):

    required: Optional[bool]
    """True: this variable is required"""

    format: Optional[str]
    """Variable format. One of ``string``, ``float``, ``int``. Default: ``string``  """

    default: Union[str, int, float, None]
    """Default value of this variable. It will be set if this variable is missing or empty"""

    min_length: Optional[int]
    """Minimum length"""

    max_length: Optional[int]
    """Maximum length"""

    min_value: Union[int, float, None]
    """Minimum value"""

    max_value: Union[int, float, None]
    """Maximum value"""

    regex: Optional[str]
    """
    If set, the value must match the Regular expression given.
    See https://docs.python.org/3/howto/regex.html. 
    """

    program: Optional[str]
    """
    Validation is limited to the given program. Default: no limitation.
    
    Use ``programs`` if validation should be limited to multiple programs.
    """

    programs: Optional[List[str]]
    """
    Validation is limited to the given programs. Default: no limitation.
    """

    def _set_range(self):
        min_value = self.min_value
        max_value = self.max_value

        if min_value and max_value and max_value < min_value:
            raise ConfigError(
                f"Expected max_value >= min_value was {max_value} < {min_value}"
            )

    def _set_programs(self):
        if self.program and self.programs:
            raise ConfigError("Expected either 'program' or 'programs' but got both.")

        self.programs = [self.program] if self.program else (self.programs or list())

    def _set_length(self):
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

    def _set_format(self):
        self.format = self.format or "string"

        SUPPORTED_FORMATS = ("string", "float", "int")

        if self.format not in SUPPORTED_FORMATS:
            formats = ", ".join(SUPPORTED_FORMATS)
            raise ConfigError(
                f"Unsuported float format. Supported formats are: {formats}"
            )

    def _set_regex(self):
        regex = self.regex
        if isinstance(regex, str):
            try:
                compile(regex)
            except ValueError as e:
                raise ConfigError(
                    f"Expected 'regex' to be a valid regex but was {regex}: {str(e)}"
                )

    def __post_init__(self):
        self.required = True if self.required is None else self.required

        self._set_regex()
        self._set_format()
        self._set_length()
        self._set_programs()
        self._set_range()


@dataclass
class ValidationSettings(object):
    """
    the validation settings

    eample:

    .. code-block:: yaml

        encab:
            debug: true
            halt_on_exit: False
        extensions:
            validation:
                enabled: true
                settings:
                    include: "validation.yml"
                    variables:
                        X:
                            required: true
                            default: "1"
                            min_length: 1
                            max_length: 5
                            regex: "0|1"
                        Y:
                            min_value: 0
                            max_value: 10


    This class contains the extensions/variables/settings content.
    """

    variables: Optional[Dict[str, Validation]]
    """ the environmant variable specifications """

    include: Optional[str]
    """ include additional environment variable specifications from file 
    
        example settings:
        
        .. code-block:: yaml
        
            settings:
                include: validation.yml
                    
        example file ``validation.yml``:
        
        .. code-block:: yaml
        
            X:
                required: true
                default: "1"
                min_length: 1
                max_length: 5
                regex: "0|1"
            Y:
                min_value: 0
                max_value: 10
        
    """

    def __post_init__(self):
        self.variables = self.variables or {}

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

    def include_validations(self) -> Dict[str, Validation]:
        """
        includes validations from an external yaml file

        :raises ConfigError: if the validation file could not be loaded
        :return: a dictionary of validations
        :rtype: Dict[str, Validation]
        """
        validations: Dict[str, Validation] = dict()
        if not self.include:
            return validations

        prefix = f"{VALIDATION}: Failed to include {self.include}"
        try:
            with open(self.include, "r") as stream:
                map = yaml.safe_load(stream)

            if not isinstance(map, dict):
                raise ConfigError(
                    f"{prefix}: Expected map as root element but got {str(map)}"
                )

            for var, validation_map in map.items():
                if not isinstance(var, str):
                    raise ConfigError(f"{prefix}: Invalid variable name {var}")

                ConfigSchema = marshmallow_dataclass.class_schema(Validation)
                validation = ConfigSchema().load(validation_map)
                assert isinstance(validation, Validation)
                validations[var] = validation

            return validations
        except YAMLError as e:
            raise ConfigError(f"{prefix}: YAML error(s) {str(e)}")
        except ValidationError as e:
            msg = e.args[0]
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"{prefix}.\n\n{VALIDATION}:\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(f"{prefix}:" + str(e.args[0]), e.args[1:])


extension_impl = HookimplMarker(ENCAB)


class VariableValidator(ABC):
    def __init__(self, name: str, validation: Validation) -> None:
        self.name = name
        self.validation = validation

    @abstractmethod
    def validate(self, value: str):
        pass

    def report_error(self, message: str) -> ConfigError:
        return ConfigError(
            f"{VALIDATION}: Validation for variable {self.name} failed: {message}."
        )


class FormatValidator(VariableValidator):
    def validate(self, value: str):
        format = self.validation.format

        if format == "string":
            pass
        elif format == "int":
            try:
                int(value)
            except ValueError:
                raise self.report_error("Expected integer format but was '{value}'")
        elif format == "float":
            try:
                float(value)
            except ValueError:
                raise self.report_error("Expected float format but was '{value}'")
        else:
            assert False, f"Unsupported format {format}."


class RangeValidator(VariableValidator):
    def validate(self, value: str):
        min_value = self.validation.min_value
        max_value = self.validation.max_value

        if not (min_value or max_value):
            return

        try:
            n = float(value)
        except ValueError:
            raise self.report_error(
                "Expected to be float (as min_value and/or max_value was given)"
                f" but was '{value}'"
            )

        if min_value and n < min_value:
            raise self.report_error("Expected {self.name} >= {min_value} but was {n}")

        if max_value and n > max_value:
            raise self.report_error(
                f"{VALIDATION}: Expected {self.name} <= {max_value} but was {n}"
            )


class LengthValidator(VariableValidator):
    def validate(self, value: str):
        min_length = self.validation.min_length
        max_length = self.validation.max_length

        if min_length and len(value) < min_length:
            raise self.report_error(
                f"Expected length >= {min_length} but was {len(value)}"
            )

        if max_length and len(value) > max_length:
            raise self.report_error(
                f"Expected length <= {max_length} but was {len(value)}"
            )


class RegexValidator(VariableValidator):
    def validate(self, value: str):
        regex = self.validation.regex

        if regex and not match(regex, value):
            raise self.report_error(f"Expected to match '{str(regex)}'")


class CombinedValidator(VariableValidator):
    def __init__(self, name: str, validation: Validation) -> None:
        super().__init__(name, validation)
        validator_classes = (
            FormatValidator,
            RangeValidator,
            LengthValidator,
            RegexValidator,
        )
        self.validators = [c(name, validation) for c in validator_classes]  # type: ignore

    def validate(self, value: str):
        for validator in self.validators:
            validator.validate(value)


class Validator(object):
    def __init__(self) -> None:
        self.settings = ValidationSettings(dict(), None)
        self.validations: Dict[str, Validation] = dict()

    def validate_names(self):
        pattern = re.compile(r"^[a-zA-Z_]+[a-zA-Z0-9_]*")
        for name in self.validations.keys():
            if not pattern.match(name):
                raise ConfigError(
                    f"{VALIDATION}: Expected valid environment variable name (see POSIX 3.231 Name)"
                    f" but was '{name}'."
                )

    def update_settings(self, settings: ValidationSettings):
        validations = settings.include_validations()
        self.validations.update(validations)
        assert settings.variables
        self.validations.update(settings.variables)
        self.validate_names()

    def validate(self, program: str, name: str, value: str):
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

        CombinedValidator(name, validation).validate(value)

    def validate_all(self, program: str, vars: Dict[str, str]):
        vars_set: Set[str] = set()

        for name, value in vars.items():
            if value:
                vars_set.add(name)
                self.validate(program, name, value)

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
                raise ConfigError(f"{VALIDATION}: Missing required parameter {name}")


class ValidationExtension(object):
    """
    Validates environment variables, sets default values and stops program execution if one or more variables
    do not conform to the specification.
    """

    def __init__(self) -> None:
        self.validator = Validator()
        self.enabled = True
        self.programs_updated: Set[str] = set()

    @extension_impl
    def validate_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name == VALIDATION:
            self.validator.update_settings(ValidationSettings.load(settings))
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
            self.validator.validate_all(program_name, environment)
        else:
            self.programs_updated.add(program_name)
