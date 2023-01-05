import sys
import os

from logging import Logger
from typing import Dict, Any, List
from pluggy import HookspecMarker, PluginManager  # type: ignore

ENCAB = "encab"

extension_method = HookspecMarker(ENCAB)


class Extensions(object):
    def __init__(
        self,
    ) -> None:
        self.plugin_manager = PluginManager(ENCAB)
        self.plugin_manager.add_hookspecs(self)
        self.hook: Any = self.plugin_manager.hook

    @extension_method
    def configure_extension(self, name: str, enabled: bool, config: Dict[str, Any]):
        self.hook.configure_extension(name=name, enabled=enabled, config=config)

    @extension_method
    def extend_environment(self, program_name: str, environment: Dict[str, str]):
        self.hook.extend_environment(program_name=program_name, environment=environment)

    @extension_method
    def update_logger(self, program_name: str, logger: Logger):
        self.hook.update_logger(program_name=program_name, logger=logger)

    def register(self, extensions: List[Any]) -> None:
        for extension in extensions:
            self.plugin_manager.register(extension)


extensions = Extensions()
