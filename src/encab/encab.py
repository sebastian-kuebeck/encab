import sys
import os
import io

from logging import (
    Logger,
    DEBUG,
    INFO,
    getLogger,
    StreamHandler,
    Formatter,
    basicConfig,
)

from signal import SIGTERM, SIGINT, signal, getsignal
from typing import Optional, List, Tuple
from textwrap import shorten
from threading import Event

from .config import Config, ConfigError
from .program import LoggingProgramObserver, ExecutionContext
from .programs import Programs


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

    if not encab_file:
        ENCAB_CONFIG = "ENCAB_CONFIG"
        if ENCAB_CONFIG in os.environ:
            encab_file = os.environ[ENCAB_CONFIG]
            source = f"Environment {ENCAB_CONFIG}"

    if not encab_file:
        ENCAB_FILE_CANDIDATES = [
            "./encab.yml",
            "./encab.yaml",
            "/etc/encab.yml",
            "/etc/encab.yaml",
        ]

        for candidate in ENCAB_FILE_CANDIDATES:
            if os.path.exists(candidate):
                encab_file = candidate
                source = f"Default location"

    if not encab_file:
        candidates = ", ".join(ENCAB_FILE_CANDIDATES)
        raise FileNotFoundError(f"Encab file not found in {candidates}.")

    if encab_stream:
        config = Config.load(encab_stream)
    else:
        with open(encab_file) as f:
            config = Config.load(f)

    return (config, f"file {encab_file}, source: {source}.")


def set_up_logger(config: Config) -> Logger:
    """
    Sets up the encab logger

    :param config: the encab configuraion
    :type config: Config
    :return: the logger
    :rtype: Logger
    """

    if config.encab:
        handler = StreamHandler()
        formatter = Formatter(config.encab.logformat)

        handler.setFormatter(formatter)
        basicConfig(level=config.encab.loglevel, handlers=[handler])

    return getLogger("encab")


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

    logger = None
    try:
        config, location = load_config(encab_stream)
        logger = set_up_logger(config)

        if config.encab:
            if config.encab.user:
                os.setuid(int(config.encab.user))

            if config.encab.umask and config.encab.umask != -1:
                os.umask(int(config.encab.umask))

        extra = {"program": "encab"}

        logger.info("encab 0.0.1", extra=extra)
        logger.info("Using configuration %s", location, extra=extra)

        logger.debug(
            "Encab config: %s",
            shorten(str(config), width=127, placeholder="..."),
            extra=extra,
        )

        program_config = config.programs or {}

        if program_config:
            logger.debug("Starting program(s)...", extra=extra)

        context = ExecutionContext(dict(os.environ))

        if config.encab and config.encab.environment:
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
            else:
                programs.terminate()
                logger.info("Programs terminated. Exiting.", extra=extra)

            exit(0)

        sigint_handler = getsignal(SIGINT)
        sigterm_handler = getsignal(SIGTERM)

        signal(SIGINT, on_signal)
        signal(SIGTERM, on_signal)

        programs.run()

        if config.encab and config.encab.halt_on_exit:
            logger.info("Programs ended. Halting for diagnose.", extra=extra)
            signal(SIGINT, sigint_handler)
            signal(SIGTERM, sigterm_handler)
            Event().wait()
        else:
            logger.debug("Programs ended. Exiting.", extra=extra)
    except FileNotFoundError as e:
        print(f"I/O Error: {str(e)}")
        exit(1)
    except ConfigError as e:
        print(f"Error in configuration: {str(e)}")
        exit(2)
    except PermissionError as e:
        print(
            f"Failed to set the encab user: {str(e)}."
            " \nTo set the user, you have to run encab as root."
        )
        exit(3)
    except KeyboardInterrupt as e:
        print(f"Encab was interrupted.")
        exit(0)


if __name__ == "__main__":
    encab()
