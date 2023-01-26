import io
import unittest

from pprint import pprint
from encab.config import Config, ProgramConfig, EncabConfig
from logging import INFO, DEBUG
from typing import cast

from encab.encab import encab, load_config

class EncabTest(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()
    
    def test_load_config(self):
        config = """
            encab:
                dry_run: true
                debug: false
                halt_on_exit: true
                loglevel: FATAL
            programs:
                main:
                    command: ['echo', 'X']
        """
        config, source = load_config(io.StringIO(config))
        self.assertEqual("file stream, source: Argument.", source)
        assert config.encab
        self.assertTrue(config.encab.dry_run)
    
    def test_encab(self):
        config = """
            encab:
                dry_run: true
                debug: false
                halt_on_exit: true
                loglevel: FATAL
            programs:
                main:
                    command: ['echo', 'X']
        """
        
        encab(encab_stream=io.StringIO(config))
