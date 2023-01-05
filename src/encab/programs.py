import sys
import os
import signal

from io import IOBase
from copy import deepcopy

from typing import Dict, Optional, List, Callable

from .config import ProgramConfig, EncabConfig, ConfigError
from .program import ExecutionContext, Program


class Programs(object):
    def __init__(
        self,
        program_configs: Dict[str, ProgramConfig],
        context: ExecutionContext,
        args: List[str],
        encab_config: Optional[EncabConfig] = None,
    ) -> None:
        main: Optional[Program] = None
        self.helpers: List[Program] = list()

        for name, program_config in program_configs.items():
            if encab_config:
                program_config.extend(encab_config)

            if name == "main":
                if args:
                    program_config.command = args
                main = Program(name, program_config, context)
            else:
                self.helpers.append(Program(name, program_config, context))

        if not main and args:
            program_config = ProgramConfig.create(command=args, environment={})

            if encab_config:
                program_config.extend(encab_config)

            main = Program("main", program_config, context)

        if not main:
            raise ConfigError(
                "No main program to run! "
                "The main program must be defined in encab.yml or passed as argument on startup!"
            )

        self.main: Program = main

    def start_helpers(self):
        for helper in self.helpers:
            helper.start(helper.config.join_time)

    def stop_helpers(self):
        for helper in reversed(self.helpers):
            helper.terminate()

        for helper in reversed(self.helpers):
            helper.join(helper.config.join_time)

    def run(
        self,
    ):
        self.start_helpers()

        self.main.start()
        self.main.join_wait()

        self.stop_helpers()

    def start(
        self,
    ):
        self.start_helpers()
        self.main.start()

    def terminate(self):
        self.main.terminate()
        self.stop_helpers()

    def interrupt(self):
        self.main.interrupt()
        self.stop_helpers()
