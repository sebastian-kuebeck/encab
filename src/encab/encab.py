import sys
import os
import io

from logging import (
    getLogger,
    StreamHandler,
    Formatter,
)

from signal import SIGTERM, SIGINT, signal, getsignal
from typing import Optional, List, Tuple, Dict
from textwrap import shorten
from threading import Event

from .common.process import Process
from .common.exit_codes import (
    EX_OK,
    EX_CONFIG_ERROR,
    EX_IOERROR,
    EX_INSUFFICIENT_PERMISSIONS,
    EX_UNKNOWN_RC,
    EX_INTERRUPTED,
    EX_TERMINATED,
)
from .config import Config, ConfigError
from .program_state import LoggingProgramObserver
from .program import ExecutionContext
from .programs import Programs
from .extensions import extensions, ENCAB

from .ext.log_sanitizer import LogSanitizerExtension
from .ext.validation import ValidationExtension
from .ext.startup_script import StarupScriptExtension
from .ext.log_collector import LogCollectorExtension


def load_config(encab_stream: Optional[io.TextIOBase] = None) -> Tuple[Config, str]:
    """
    Loads the configuration file

    :param encab_stream: _description_, defaults to None
    :type encab_stream: Optional[io.TextIOBase], optional
    :raises FileNotFoundError: _description_
    :return: _description_
    :rtype: Tuple[Config, str]
    """

    encab_file = None

    if encab_stream is not None:
        encab_file = "stream"

    source = "Argument"

    ENCAB_CONFIG = "ENCAB_CONFIG"

    if not encab_file:
        if ENCAB_CONFIG in os.environ:
            encab_file = os.environ[ENCAB_CONFIG]
            source = f"Environment {ENCAB_CONFIG}"

    ENCAB_FILE_CANDIDATES = [
        "./encab.yml",
        "./encab.yaml",
        "/etc/encab.yml",
        "/etc/encab.yaml",
    ]

    if not encab_file:
        for candidate in ENCAB_FILE_CANDIDATES:
            if os.path.exists(candidate):
                encab_file = candidate
                source = "Default location"

    if not encab_file:
        candidates = ", ".join(ENCAB_FILE_CANDIDATES)
        raise FileNotFoundError(f"Encab file not found in {candidates}.")

    if encab_stream:
        config = Config.load(encab_stream)
    else:
        with open(encab_file, "r") as f:
            config = Config.load(f)

    ENCAB_DRY_RUN = "ENCAB_DRY_RUN"

    dry_run = None
    if ENCAB_DRY_RUN in os.environ:
        value = os.environ[ENCAB_DRY_RUN]
        if not value:
            pass
        elif value == "1":
            dry_run = True
        elif value == "0":
            dry_run = False
        else:
            raise ConfigError(
                "Environment variable ENCAB_DRY_RUN"
                " expected to be '1' or '0' if set"
                f" but was '{value}'."
            )

    assert config.encab
    if dry_run is not None:
        config.encab.dry_run = dry_run

    return (config, f"file {encab_file}, source: {source}.")


def set_up_logger(config: Config):
    """
    Sets up the encab logger

    :param config: the encab configuraion
    :type config: Config
    :return: the logger
    :rtype: Logger
    """

    if config.encab:
        root_logger = getLogger()

        handler = StreamHandler()
        formatter = Formatter(config.encab.logformat)

        handler.setFormatter(formatter)

        loglevel = config.encab.loglevel
        assert isinstance(loglevel, int) or isinstance(loglevel, str)

        root_logger.setLevel(loglevel)
        root_logger.addHandler(handler)

    logger = getLogger(ENCAB)
    extensions.update_logger(ENCAB, logger)
    return logger


def set_up_extensions(config: Config, logger, extra: Dict[str, str]):
    """
    sets up and configures the extensions.
    In case of dry run, `encab.extensions.Extensions.validate_extension` instead of
    `encab.extensions.Extensions.configure_extension` is run for each plugin.

    :param config: the encab config
    :type config: Config
    :param logger: the logger to be used
    :type logger: Logger
    :param extra: the logger extension
    :type extra: Dict[str, str]
    """

    if config.extensions:
        assert config.encab and isinstance(config.encab.dry_run, bool)
        dry_run = config.encab.dry_run

        for name, econf in config.extensions.items():
            if econf.module:
                extensions.register_module(econf.module)

            assert isinstance(econf.enabled, bool)

            if dry_run:
                extensions.validate_extension(name, econf.enabled, econf.settings or {})
            else:
                extensions.configure_extension(
                    name, econf.enabled, econf.settings or {}
                )


def encab(
    encab_stream: Optional[io.TextIOBase] = None, args: Optional[List[str]] = None
):
    """
    Encab's main routine

    - loads the configuration file
    - replaces the main program with the one from arguments if specified
    - runs the programs

    :param encab_stream: the configruration as text stream, defaults to None
    :type encab_stream: Optional[io.TextIOBase], optional
    :param args: the main program arguments, defaults to None
    :type args: Optional[List[str]], optional
    """

    extensions.register(
        [
            StarupScriptExtension(),
            LogSanitizerExtension(),
            ValidationExtension(),
            LogCollectorExtension(),
        ]
    )

    logger = None
    try:
        config, location = load_config(encab_stream)

        logger = set_up_logger(config)

        extra = {"program": ENCAB}

        logger.info("encab 0.1.5", extra=extra)
        logger.info("Using configuration %s", location, extra=extra)

        logger.debug(
            "Encab config: %s",
            shorten(str(config), width=127, placeholder="..."),
            extra=extra,
        )

        assert config.encab and isinstance(config.encab.dry_run, bool)
        dry_run = config.encab.dry_run

        if dry_run:
            logger.info("Dry run. No program will be started.", extra=extra)

        set_up_extensions(config, logger, extra)

        if dry_run:
            logger.info("Dry run succeeded. Exiting.", extra=extra)
            return

        config.encab.set_user()
        config.encab.set_group()

        assert config.encab.user is None or isinstance(config.encab.user, int)
        assert config.encab.group is None or isinstance(config.encab.group, int)
        assert config.encab.umask is None or isinstance(config.encab.umask, int)

        Process.update_current(
            config.encab.user, config.encab.group, config.encab.umask
        )

        program_config = config.programs or {}

        if program_config:
            logger.debug("Starting program(s)...", extra=extra)

        observer = LoggingProgramObserver(ENCAB, logger, extra)
        context = ExecutionContext(dict(os.environ), observer)

        if config.encab.environment:
            context = context.extend(config.encab.environment)

        args = args if args is not None else sys.argv[1:]

        programs = Programs(program_config, context, args, config.encab)

        def on_signal(signal, _):
            signames = {SIGINT: "SIGINT", SIGTERM: "SIGTERM"}

            logger.info(
                "Received %s. Interrupting/terminating programs...",
                signames[signal],
                extra=extra,
            )

            if signal == SIGINT:
                programs.interrupt()
                logger.info("Programs interrupted. Exiting.", extra=extra)
                exit(EX_INTERRUPTED)
            else:
                programs.terminate()
                logger.info("Programs terminated. Exiting.", extra=extra)
                exit(EX_TERMINATED)

        sigint_handler = getsignal(SIGINT)
        sigterm_handler = getsignal(SIGTERM)

        signal(SIGINT, on_signal)
        signal(SIGTERM, on_signal)

        programs.run()

        if config.encab.halt_on_exit:
            logger.info("Programs ended. Halting for diagnose.", extra=extra)
            signal(SIGINT, sigint_handler)
            signal(SIGTERM, sigterm_handler)
            Event().wait()
        else:
            logger.debug("Programs ended. Exiting.", extra=extra)

        exit(programs.exit_code if programs.exit_code is not None else EX_UNKNOWN_RC)
    except PermissionError as e:
        print(
            f"Failed to set the encab user: {str(e)}."
            " \nTo set the user, you have to run encab as root."
        )
        exit(EX_INSUFFICIENT_PERMISSIONS)
    except IOError as e:
        print(f"I/O Error: {str(e)}")
        exit((EX_IOERROR))
    except ValueError as e:
        print(f"Error in configuration: {str(e)}")
        exit(EX_CONFIG_ERROR)
    except KeyboardInterrupt:
        print("Encab was interrupted.")
        exit(EX_OK)


if __name__ == "__main__":
    encab()
