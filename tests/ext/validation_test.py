import unittest

from typing import Set, Dict, Any, Optional, List
from logging import LogRecord, INFO

from encab.ext.validation import ValidationSettings, Validator


class ValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    """
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
    """

    def test_settings(self):
        settings = ValidationSettings.load(
            {
                "variables": {
                    "X": {
                        "required": True,
                        "default": "1",
                        "min_length": 1,
                        "max_length": 5,
                        "regex": "0|1",
                    },
                    "Y": {
                        "format": "int",
                        "min_value": 1,
                        "max_value": 5,
                    },
                }
            }
        )
        self.assertEqual(["X", "Y"], list(settings.variables.keys()))

        x = settings.variables["X"]
        self.assertEqual("string", x.format)

        x = settings.variables["X"]
        self.assertEqual("int", x.format)
