import os
import pwd
import grp
import unittest


class EncabProcessTest(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def test_user(self):
        entry = pwd.getpwuid(os.geteuid())
        self.assertEqual("runner", entry.pw_name)

    def test_group(self):
        entry = grp.getgrgid(os.getgid())
        self.assertEqual("runners", entry.gr_name)

    def test_umask(self):
        current_umask = os.umask(0o022)
        os.umask(current_umask)
        self.assertEqual(0o001, current_umask)
