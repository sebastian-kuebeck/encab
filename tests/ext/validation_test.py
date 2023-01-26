import unittest
import os

from typing import Set, Dict, Any, Optional, List
from logging import LogRecord, INFO

from encab.ext.validation import ValidationSettings, Validator, ConfigError


class ValidationTest(unittest.TestCase):
    settings: ValidationSettings
    validator: Validator

    def setUp(self) -> None:
        super().setUp()

        self.settings = ValidationSettings.load(
            {
                "variables": {
                    "X": {
                        "required": True,
                        "default": "A",
                        "min_length": 1,
                        "max_length": 5,
                    },
                    "Y": {
                        "format": "int",
                        "min_value": 1,
                        "max_value": 5,
                    },
                    "Z": {"required": False, "regex": "1|2|3"},
                    "W1": {
                        "format": "float",
                        "default": "B",
                        "required": False,
                        "program": "foo",
                    },
                    "W2": {
                        "format": "float",
                        "default": "C",
                        "required": False,
                        "programs": ["foo", "bar"],
                    },
                }
            }
        )

        self.validator = Validator()
        self.validator.update_settings(self.settings)

    def assertValid(self, vars: Dict[str, str], program="main"):
        try:
            self.validator.validate_all(program, vars)
        except ConfigError as e:
            self.fail(f"Expected {vars} to be valid but got: {str(e)}")

    def assertInvalid(self, vars: Dict[str, str], program="main"):
        try:
            self.validator.validate_all(program, vars)
            self.fail(f"Expected {vars} to be invalid")
        except ConfigError as e:
            pass

    def test_settings(self):
        settings = self.settings
        assert settings.variables
        
        self.assertEqual(["X", "Y", "Z", "W1", "W2"], list(settings.variables.keys()))

        x = settings.variables["X"]
        self.assertEqual("string", x.format)
        self.assertTrue(x.required)

        y = settings.variables["Y"]
        self.assertEqual("int", y.format)
        self.assertTrue(y.required)

        z = settings.variables["Z"]
        self.assertEqual("string", z.format)
        self.assertFalse(z.required)

        w1 = settings.variables["W1"]
        self.assertEqual(["foo"], w1.programs)

        w2 = settings.variables["W2"]
        self.assertEqual(["foo", "bar"], w2.programs)

    def test_validate_all(self):
        self.assertValid({"X": "1", "Y": "2", "Z": "3"})
        
    def test_validate_required(self):
        self.assertValid({"X": "1", "Y": "2"})
        self.assertInvalid({"Z": "3"})

    def test_validate_program(self):
        self.assertValid({"Y": "2", "W1": "1"}, "foo")
        self.assertInvalid({"Y": "2", "W1": "A"}, "foo")

    def test_validate_programs(self):
        self.assertValid({"Y": "2", "W1": "1", "W2": "1"}, "foo")
        self.assertInvalid({"Y": "2", "W2": "A"}, "bar")

    def test_validate_default(self):
        vars = {"Y": "2"}
        self.assertValid(vars)
        self.assertEqual({"Y": "2", "X": "A"}, vars)
        
    def test_validate_length(self):
        self.assertValid({"Y": "2", "X": "A"})
        self.assertInvalid({"Y": "2", "X": "123456"})
        
    def test_validate_range(self):
        self.assertValid({"Y": "1"})
        self.assertInvalid({"Y": "0"})
        self.assertInvalid({"Y": "6"})

    def test_validate_regex(self):
        self.assertValid({"Y": "1", "Z": "1"})
        self.assertInvalid({"Y": "1", "Z": "4"})
        self.assertInvalid({"Y": "1", "Z": "A"})
        
    def test_include(self):
        ext_path = os.path.dirname(__file__)
        validation_file = os.path.join(ext_path, "validation.yml")
        
        self.settings = ValidationSettings.load(
            {
                "include": validation_file
            }
        )

        validations = self.settings.include_validations()
        self.assertEqual(['X', 'Y'], list(validations.keys()))
        
