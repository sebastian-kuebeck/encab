import os
import sys
import re
import yaml
import marshmallow_dataclass

from io import StringIO
from typing import Dict, List, Any, Optional, Union, IO
from logging import Logger, getLogger, INFO, ERROR
from pluggy import HookimplMarker  # type: ignore

from dataclasses import dataclass
from marshmallow.exceptions import MarshmallowError, ValidationError

from dotenv import dotenv_values
from threading import Thread
from subprocess import Popen, PIPE

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


class LogStream(object):
    """
    Reads from a stream in a background thread and loggs the result line by line
    """

    def __init__(
        self, logger: Logger, log_level: int, stream: IO[bytes], extra: Dict[str, str]
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
        except OSError:
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
        return self

    def close(self):
        self.stream.close()


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

        out: Optional[LogStream] = None
        err: Optional[LogStream] = None
        try:
            with Popen(
                script, stdout=PIPE, stderr=PIPE, env=environment, shell=True
            ) as process:
                assert process.stderr
                assert process.stdout

                err = LogStream(mylogger, ERROR, process.stderr, extra).start()
                out = LogStream(mylogger, INFO, process.stdout, extra).start()

                process.wait()

                exit_code = process.returncode
                if exit_code != 0:
                    raise IOError(
                        f"{STARTUP_SCRIPT}: Startup script failed with exit code: {exit_code}"
                    )

        except BaseException as e:
            raise IOError(f"{STARTUP_SCRIPT}: Failed to execute startup script: {e}")
        finally:
            if out:
                out.close()
            if err:
                err.close()

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

        err: Optional[LogStream] = None
        lines: List[str] = list()
        try:
            with Popen(
                script, stderr=PIPE, stdout=PIPE, env=environment, shell=True
            ) as process:
                assert process.stdout is not None
                assert process.stderr is not None

                err = LogStream(mylogger, ERROR, process.stderr, extra).start()

                for line in process.stdout:
                    strline = line.decode(sys.getdefaultencoding()).rstrip("\r\n\t ")
                    lines.append(strline)

                process.wait()
                exit_code = process.returncode
                if exit_code != 0:
                    raise IOError(f"Buildenv script failed with exit code: {exit_code}")

        except BaseException as e:
            raise IOError(f"{STARTUP_SCRIPT}: Failed to execute buildenv script: {e}")
        finally:
            if err:
                err.close()

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
