import yaml
import marshmallow_dataclass

from typing import Dict, Set, List, Any, Mapping, Tuple, cast, Optional
from logging import getLogger
from pluggy import HookimplMarker  # type: ignore

"""
Trivial Module extension for testing purposes
"""

ENCAB = "encab"
TEST_MODULE_EXTENSION = "test_module_extension"

mylogger = getLogger(TEST_MODULE_EXTENSION)

extension_impl = HookimplMarker(ENCAB)


@extension_impl
def validate_extension(name: str, enabled: bool, settings: Dict[str, Any]):
    if name == TEST_MODULE_EXTENSION:
        mylogger.info("Text extension: settings are valid.", extra={"program": ENCAB})


@extension_impl
def configure_extension(name: str, enabled: bool, settings: Dict[str, Any]):
    if name == TEST_MODULE_EXTENSION:
        mylogger.info("Text extension: Here I am!", extra={"program": ENCAB})


@extension_impl
def extend_environment(program_name: str, environment: Dict[str, str]):
    if program_name == TEST_MODULE_EXTENSION:
        mylogger.info("Text extension: Here I am!", extra={"program": ENCAB})
