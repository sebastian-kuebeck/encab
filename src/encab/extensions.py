from logging import Logger
from typing import Dict, Any, List
from importlib import import_module
from pluggy import HookspecMarker, PluginManager, PluginValidationError  # type: ignore


ENCAB = "encab"

extension_method = HookspecMarker(ENCAB)


class Extensions(object):
    """
    Represents the connection point between encab and its extensions

    Extension methods specified here are implemented by extensions

    example extension code:

    .. code-block:: python

        from pluggy import HookimplMarker  # type: ignore

        ENCAB = "encab"
        extension_impl = HookimplMarker(ENCAB)

        @extension_impl
        def validate_extension(
            self,
            name: str,
            enabled: bool,
            config: Dict[str, Any]):
            '''
                your implementation
            '''
            pass

    """

    def __init__(
        self,
    ) -> None:
        self.plugin_manager = PluginManager(ENCAB)
        self.plugin_manager.add_hookspecs(self)
        self.hook: Any = self.plugin_manager.hook

    @extension_method
    def validate_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        """
        similar to :meth:`encab.extensions.Extensions.configure_extension`
        but the extension validates it's configuration during a dry run,
        where the extension isn't actually startet.

        see :meth:`encab.extensions.Extensions.configure_extension` for details.

        :param name: the extension name
        :type name: str
        :param enabled: if True: the extension is enabled
        :type enabled: bool
        :param settings: the extension settings from the encab config
        :type settings: Dict[str, Any]
        """
        self.hook.validate_extension(name=name, enabled=enabled, settings=settings)

    @extension_method
    def configure_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        """
        configure_extension is called on startup for each extension.
        The extension picks up its own settings from the parameter ``config``
        by selecting for the name.

        Depening on the flag ``enabled``, each extension enables or disables its service.

        Encab config example:

        .. code-block:: yaml

            encab:
                debug: true
                halt_on_exit: False
            extensions:
                my_extension:
                    enabled: true
                    settings:
                        foo: bar


        The path for the settings is ``/extensions/<name>/settings``
        In this example, ``name``: would be ``my_extension`` and
        ``settings`` would be ``{'foo':'bar'}``.

        The extension will validate its settings and throw a ValueError (or a derivative thereof)
        with a descriptive error message if extension settings are invalid.

        :param name: the extension name
        :type name: str
        :param enabled: if True: the extension is enabled
        :type enabled: bool
        :param settings: the extension settings from the encab config
        :type settings: Dict[str, Any]
        """
        self.hook.configure_extension(name=name, enabled=enabled, settings=settings)

    @extension_method
    def extend_environment(self, program_name: str, environment: Dict[str, str]):
        """
        extend_environment is called whenever the environment of encab or a program
        (indicated by ``program_name``) is extended.

        The extension is free to alter the environment.

        :param program_name: the program name indicating the program the environment belongs to
        :type program_name: str
        :param environment: the environment as mutable dictionary
        :type environment: Dict[str, str]
        """
        self.hook.extend_environment(program_name=program_name, environment=environment)

    @extension_method
    def update_logger(self, program_name: str, logger: Logger):
        """
        update_logger is called whenever a logger for a program is introduced.

        The extension is free to alter the logger, e.g. by adding custom handlers.

        :param program_name: the logger's program name
        :type program_name: str
        :param logger: the newly introduced logger
        :type logger: Logger
        """
        self.hook.update_logger(program_name=program_name, logger=logger)

    def register(self, extensions: List[Any]) -> None:
        """
        register new extension as object or module

        :param extensions: a list of extension objects and/or modules
        :type extensions: List[Any]
        """
        for extension in extensions:
            self.plugin_manager.register(extension)

    def register_module(self, module_name: str):
        try:
            module = import_module(module_name)
            self.plugin_manager.register(module)
        except ModuleNotFoundError:
            raise FileNotFoundError(f"Extension module {module_name} not found")
        except ImportError as e:
            raise IOError(f"Failed to load extension module {module_name}: {str(e)}")
        except PluginValidationError as e:
            raise IOError(f"Failed to load extension module {module_name}: {str(e)}")


extensions = Extensions()
"""The singleton instance that's used by encab to call extension methods"""
