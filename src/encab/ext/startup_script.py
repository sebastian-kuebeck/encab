import os
import sys
import yaml
import marshmallow_dataclass

from fnmatch import fnmatch
from io import TextIOBase, StringIO
from typing import Dict, Set, List, Any, Mapping, Tuple, cast, Optional, Union
from logging import Logger, Filter, LogRecord, getLogger, INFO, ERROR, DEBUG
from pluggy import HookimplMarker  # type: ignore

from yaml.error import YAMLError
from dataclasses import dataclass, fields
from marshmallow.exceptions import MarshmallowError, ValidationError
from abc import ABC

from dotenv import dotenv_values
from threading import Thread
from subprocess import Popen, PIPE
from io import IOBase

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
    buildenv: Union[List[str], str, None]
    sh: Union[List[str], str, None]

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


class LogStream(object):
    """
    Reads from a stream in a background thread and loggs the result line by line
    """

    def __init__(
        self, logger: Logger, log_level: int, stream: IOBase, extra: Dict[str, str]
    ) -> None:
        """
        :param Logger logger: the logger to which the stream content is written
        :param int log_level: the log level (see Python logging)
        :param IOBase stream: the stream that is logged
        :param Dict[str, str] extra: extra information that is logged each line (see Python logging)
        """
        self.logger = logger
        self.log_level = log_level
        self.stream = stream
        self.extra = extra
        self.thread: Optional[Thread] = None

    def _run(self):
        try:
            for line in self.stream:
                strline = line.decode(sys.getdefaultencoding()).rstrip("\r\n\t ")
                self.logger.log(self.log_level, strline, extra=self.extra)
        except ValueError:
            pass  # stream was closed
        except OSError as e:
            self.logger.exception(
                "I/O Error while logging: %s", self.name, extra=self.extra  # type: ignore
            )
        except:
            self.logger.exception(
                "Something went wrong while logging", extra=self.extra
            )
            raise

    def start(self):
        """starts reading and logging"""
        program = self.extra.get("program", "")
        name = f"{program}:{self.log_level}"
        thread = Thread(target=lambda: self._run(), name=name)
        thread.daemon = True
        self.thread = thread
        thread.start()


class StartupScript:
    def __init__(self) -> None:
        self.settings: Optional[StartupScriptSettings] = None
        self.executed = False

    def update_settings(self, settings: StartupScriptSettings):
        self.settings = settings

    def loadenv(self, environment: Dict[str, str]):
        if not self.settings:
            return

        path = self.settings.loadenv

        if not path:
            return

        if not os.path.isfile(path):
            raise ConfigError(f"File {path} defined by loadenv does not exist")

        mylogger.info("Loading env file: %s", path, extra={"program": ENCAB})

        try:
            env = dotenv_values(path)

            if isinstance(env, dict):
                env = {str(k): str(v or "") for k, v in env.items() if k}
                mylogger.debug(
                    "Adding environment: %s", str(dict(env)), extra={"program": ENCAB}
                )
                environment.update(cast(Dict[str, str], env))

        except IOError as e:
            raise IOError(
                f"Failed to load environment specified in loadenv from {path}"
            )

    def sh(self, environment: Dict[str, str]):
        if not self.settings:
            return

        sh = self.settings.sh

        if not sh:
            return

        script = "; ".join(sh)

        extra = {"program": "startup_script/sh"}

        try:
            with Popen(
                script,
                stdout=PIPE,
                stderr=PIPE,
                env=environment,
                shell=True,
                start_new_session=True,
            ) as process:
                LogStream(mylogger, ERROR, cast(IOBase, process.stderr), extra).start()
                LogStream(mylogger, INFO, cast(IOBase, process.stdout), extra).start()

                process.wait()

                exit_code = process.returncode
                if exit_code != 0:
                    raise IOError(f"Startup script failed with exit code: {exit_code}")

        except BaseException as e:
            raise IOError(f"Failed to execute startup script: {e}")

    def buildenv(self, environment: Dict[str, str]):
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
            with Popen(
                script,
                stderr=PIPE,
                stdout=PIPE,
                env=environment,
                shell=True,
                start_new_session=True,
            ) as process:
                LogStream(mylogger, ERROR, cast(IOBase, process.stderr), extra).start()

                for line in cast(IOBase, process.stdout):
                    strline = line.decode(sys.getdefaultencoding()).rstrip("\r\n\t ")
                    lines.append(strline)

                process.wait()
                exit_code = process.returncode
                if exit_code != 0:
                    raise IOError(f"Buildenv script failed with exit code: {exit_code}")

        except BaseException as e:
            raise IOError(f"Failed to execute buildenv script: {e}")

        try:
            stream = StringIO("\n".join(lines))
            env = dotenv_values(stream=stream)

            if isinstance(env, dict):
                env = {str(k): str(v or "") for k, v in env.items() if k}
                mylogger.debug(
                    "Adding environment: %s", str(dict(env)), extra={"program": ENCAB}
                )
                environment.update(cast(Dict[str, str], env))
                
        except IOError as e:
            raise IOError(f"Failed to load environment specified in buieldenv: {e}")

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