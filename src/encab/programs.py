from typing import Dict, Optional, List

from .config import ProgramConfig, EncabConfig, ConfigError
from .program import ExecutionContext, Program


class Programs(object):
    """
    controls the lifecycles of all configured programs
    """

    def __init__(
        self,
        program_configs: Dict[str, ProgramConfig],
        context: ExecutionContext,
        args: List[str],
        encab_config: Optional[EncabConfig] = None,
    ) -> None:
        """
        creates a programs instance and sets/replaces
        the main program form the arguments.

        :param program_configs: the program configurations
        :type program_configs: Dict[str, ProgramConfig]
        :param context: the root program context
        :type context: ExecutionContext
        :param args: the command line arguments
        :type args: List[str]
        :param encab_config: the basic encab config, defaults to None
        :type encab_config: Optional[EncabConfig], optional
        :raises ConfigError: If programs connot find a program to run
        """
        main: Optional[Program] = None
        self.helpers: List[Program] = list()

        for name, program_config in program_configs.items():
            if encab_config:
                program_config.extend(encab_config)
                program_config.set_user()

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
        """
        runs the programs as configured and waits until the main program has stopped.
        """
        self.start_helpers()

        self.main.start()
        self.main.join_wait()

        self.stop_helpers()

    def start(
        self,
    ):
        """
        starts the programs as configured
        """

        self.start_helpers()
        self.main.start()

    def terminate(self):
        """
        terminates the main program and stops the helpers
        """
        self.main.terminate()
        self.stop_helpers()

    def interrupt(self):
        """
        interrupts the main program and stops the helpers
        """
        self.main.interrupt()
        self.stop_helpers()
