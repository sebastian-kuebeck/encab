import io
import unittest

from encab.config import Config, ProgramConfig, EncabConfig
from logging import DEBUG


class ConfigTest(unittest.TestCase):
    def test_from_constructor(self):
        programs = {
            "cron": ProgramConfig.create(command="cron -f", startup_delay=5.2),
            "main": ProgramConfig.create(command="httpd-foreground"),
        }

        encab = EncabConfig.create(debug=True, umask="077")

        for _, program in programs.items():
            program.extend(encab)

        self.assertEqual(DEBUG, encab.loglevel)
        self.assertIsNone(encab.user)
        self.assertEqual(0o077, encab.umask)
        self.assertEqual(1, encab.join_time)

        c = Config.create(programs=programs, encab=encab)
        programs = c.programs or {}

        self.assertEqual(["cron", "-f"], programs["cron"].command)
        self.assertEqual(5.2, programs["cron"].startup_delay)

        self.assertEqual(["httpd-foreground"], programs["main"].command)
        self.assertEqual(0.0, programs["main"].startup_delay)

    def test_from_yaml(self):
        file = """
            programs:
                cron:
                    command: cron -f
                main:
                    command: httpd-foreground
            """
        c = Config.load(io.StringIO(file))
        programs = c.programs or {}
        self.assertEqual(["cron", "-f"], programs["cron"].command)
        self.assertEqual(["httpd-foreground"], programs["main"].command)
