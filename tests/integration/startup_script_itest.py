import os
import unittest


class StartupScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def test_environment(self):
        """
        Test environment specified in encab config
        """
        e = os.environ
        self.assertTrue("1", e["X"])
        self.assertTrue("2", e["Y"])
        self.assertTrue("3", e["Z"])
