import os
import sys
import re
import yaml
import marshmallow_dataclass

from io import StringIO
from typing import Dict, List, Any, Optional, Union
from logging import getLogger
from pluggy import HookimplMarker  # type: ignore

from dataclasses import dataclass
from marshmallow.exceptions import MarshmallowError, ValidationError

from dotenv import dotenv_values
from subprocess import Popen

from encab.common.process import Process

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
            startup_script:
                enabled: true
                settings:
                    loadenv:
                        .env
                    buildenv:
                        - echo "X=1"
                    sh:
                        - echo $X

    This class contains the extensions/startup_script/settings content.
    """

    loadenv: Optional[str]
    """
    the path of the file in dotenv format from which environment variables are loaded.
    The format is similar to Bash files.
    
    Example:
    
    .. code-block:: bash
    
        FOO="first line"
        BAR=2
    
    see: https://pypi.org/project/python-dotenv/
    
    """

    buildenv: Union[List[str], str, None]
    """
    executes a shell command that generates environment variables in dotenv format.
    
    Example:
    
    .. code-block:: yaml
    
        buildenv:
        - echo "X=1"
        - echo "Y=2"
    """

    sh: Union[List[str], str, None]
    """
    executes a shell command before the programs specified in the programs section of the encab file are run
    """

    def __post_init__(self):
        if isinstance(self.buildenv, str):
            self.buildenv = [self.buildenv]

        if isinstance(self.sh, str):
            self.sh = [self.sh]

    @staticmethod
    def load(settings: Dict[str, Any]) -> "StartupScriptSettings":
        try:
            ConfigSchema = marshmallow_dataclass.class_schema(StartupScriptSettings)
            return ConfigSchema().load(settings)  # type: ignore
        except ValidationError as e:
            msg = e.args[0]  # type: ignore
            if isinstance(msg, dict):
                msg = yaml.dump(msg, default_flow_style=False)

            raise ConfigError(f"\n\n{STARTUP_SCRIPT}:\n{msg}")
        except MarshmallowError as e:
            raise ConfigError(e.args)


class StartupScript:
    """
    Run scripts before the actual programs are started.
    In addition, environman variables can be loaded from a file or generated
    using a script.
    """

    def __init__(self) -> None:
        self.settings: Optional[StartupScriptSettings] = None
        self.executed = False

    def update_settings(self, settings: StartupScriptSettings):
        self.settings = settings

    def loadenv(self, environment: Dict[str, str]):
        """
        loads the environment from a file if the plugin settings demand it

        :param environment: the environment
        :type environment: Dict[str, str]
        :raises ConfigError: if the file could not be loaded
        """
        if not self.settings:
            return

        path = self.settings.loadenv

        if not path:
            return

        if not os.path.isfile(path):
            raise ConfigError(
                f"{STARTUP_SCRIPT}: File {path} defined by loadenv does not exist"
            )

        mylogger.info("Loading env file: %s", path, extra={"program": ENCAB})

        self.update_env(environment, path=path)

    def update_env(
        self,
        environment: Dict[str, str],
        path: Optional[str] = None,
        stream: Optional[StringIO] = None,
    ):
        """
        validates and updates the environment form a file or stream in dotenv_ format

        .. _dotenv: https://pypi.org/project/python-dotenv/

        :param environment: the environment
        :type environment: Dict[str, str]
        :param path: the path from which the environment should be loaded, defaults to None
        :type path: Optional[str], optional
        :param stream: _description_, defaults to None
        :type stream: Optional[StringIO], optional
        :raises IOError: if the environment could not be loaded
        """
        try:
            if path:
                values = dotenv_values(dotenv_path=path)
            else:
                assert stream
                values = dotenv_values(stream=stream)

            if isinstance(values, dict):
                env = self.clean_up_env(values)
                mylogger.debug(
                    "Adding environment: %s", str(env), extra={"program": ENCAB}
                )
                environment.update(env)

        except IOError:
            raise IOError(
                f"{STARTUP_SCRIPT}: Failed to load environment specified in loadenv from {path}"
            )

    def clean_up_env(self, values: Dict[Any, Any]) -> Dict[str, str]:
        """
        returns the environment variable dictionary such that it can be safely used by programs

        :param values: the raw dictionary
        :type values: Dict[Any, Any]
        :raises ConfigError: if a variable name does not comply with POSIX 3.231 Name
        :return: the cleaned up and validated environment variable dictionary
        :rtype: Dict[str, str]
        """
        env = dict()
        pattern = re.compile(r"^[a-zA-Z_]+[a-zA-Z0-9_]*")
        for k, v in values.items():  # type: ignore
            name = str(k)
            if not pattern.match(name):
                raise ConfigError(
                    f"{STARTUP_SCRIPT}: Expected valid environment variable name (see POSIX 3.231 Name)"
                    f" but was '{name}'."
                )
            env[name] = "" if v is None else str(v)
        return env

    def sh(self, environment: Dict[str, str]):
        """
        runs the script with the given environment if the plugin settings demand it

        :param environment: the environment
        :type environment: Dict[str, str]
        :raises IOError: if the script execution fails
        """
        if not self.settings:
            return

        sh = self.settings.sh

        if not sh:
            return

        script = "; ".join(sh)

        extra = {"program": "startup_script/sh"}

        try:
            process = Process(script, environment, shell=True)
            exit_code = process.execute_and_log(lambda _: None, mylogger, extra)

            if exit_code != 0:
                raise IOError(
                    f"{STARTUP_SCRIPT}: Startup script failed with exit code: {exit_code}"
                )
        except BaseException as e:
            raise IOError(f"{STARTUP_SCRIPT}: Failed to execute startup script: {e}")

    def buildenv(self, environment: Dict[str, str]):
        """
        runs the buildenv script, processes and updates the current environment

        :param environment: the environment
        :type environment: Dict[str, str]
        :raises IOError: if the script execution fails
        """

        if not self.settings:
            return

        buildenv = self.settings.buildenv

        if not buildenv:
            return

        script = "; ".join(buildenv)

        extra = {"program": "startup_script/buildenv"}

        mylogger.info("Running buildenv script", extra={"program": ENCAB})

        lines: List[str] = list()
        try:

            def read_lines(process: Popen):
                assert process.stdout
                with process.stdout as stdout:
                    for line in stdout:
                        strline = line.decode(sys.getdefaultencoding()).rstrip(
                            "\r\n\t "
                        )
                        lines.append(strline)

            process = Process(script, environment, shell=True)

            exit_code = process.execute_and_log(
                read_lines, mylogger, extra, log_stdout=False
            )

            if exit_code != 0:
                raise IOError(f"Buildenv script failed with exit code: {exit_code}")

        except BaseException as e:
            raise IOError(f"{STARTUP_SCRIPT}: Failed to execute buildenv script: {e}")

        self.update_env(environment, stream=StringIO("\n".join(lines)))

    def execute(self, environment: Dict[str, str]):
        if self.executed:
            return

        self.executed = True

        self.loadenv(environment)
        self.buildenv(environment)
        self.sh(environment)


extension_impl = HookimplMarker(ENCAB)


class StarupScriptExtension(object):
    def __init__(self) -> None:
        self.script = StartupScript()
        self.enabled = True

    @extension_impl
    def validate_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name == STARTUP_SCRIPT:
            StartupScriptSettings.load(settings)
            mylogger.info("settings are valid.", extra={"program": ENCAB})

    @extension_impl
    def configure_extension(self, name: str, enabled: bool, settings: Dict[str, Any]):
        if name != STARTUP_SCRIPT:
            return

        if not enabled:
            self.enabled = False
            return

        self.script.update_settings(StartupScriptSettings.load(settings))

    @extension_impl
    def extend_environment(self, program_name: str, environment: Dict[str, str]):
        if not self.enabled:
            return

        self.script.execute(environment)
