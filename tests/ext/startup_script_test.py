import os
import unittest

from typing import Set, Dict, Any, Optional, List
from logging import LogRecord, INFO

from encab.ext.startup_script import StartupScript, StartupScriptSettings, ConfigError

class StartupScriptTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
                
    def script(self, conf: Dict[str, Any]):
        settings = StartupScriptSettings.load(conf)
        script = StartupScript()
        script.update_settings(settings)
        return script

    def test_buildenv(self) -> None:
        env: Dict[str, str] = dict()
        
        script = self.script({
            'buildenv': 'echo "X=1"'
        })
        
        script.execute(env)
        self.assertEqual({'X': '1'}, env)
        
    def test_invalid_variable_name(self) -> None:
        env: Dict[str, str] = dict()
        
        script = self.script({
            'buildenv': 'echo "%X=1"'
        })
                
        try:
            script.execute(env)
            self.fail(f"Should fail but got {str(env)}")
        except ConfigError as e:
            pass
        
    def test_loadenv(self) -> None:
        ext_path = os.path.dirname(__file__)
        dotenv_file = os.path.join(ext_path, "test.dotenv")
        env: Dict[str, str] = dict()
        
        script = self.script({
            'loadenv': dotenv_file
        })
        
        script.execute(env)
        self.assertEqual({'X': '1', 'Y': '2'}, env)
        
    def test_sh(self) -> None:
        env: Dict[str, str] = dict()
        
        script = self.script({
            'sh': 'echo X'
        })
        
        script.execute(env)
