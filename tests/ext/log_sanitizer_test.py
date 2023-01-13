import unittest

from typing import Set, Dict, Any, Optional, List
from logging import LogRecord, INFO

from encab.ext.log_sanitizer import (
    LogSanitizerConfig,
    SanitizingFilter,
    LogSanititerExtension,
    LOG_SANITIZER,
)


class LogSanititerTest(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def test_config(self):
        config = LogSanitizerConfig.load({"patterns": ["x*"], "override": True})
        self.assertEqual(["x*"], config.patterns)
        self.assertTrue(config.override)

    def test_config_defaults(self):
        config = LogSanitizerConfig.load({})
        self.assertEqual([], config.patterns)
        self.assertFalse(config.override)

    def sanitize(self, sensitive_strings: Set[str], msg: str, *args) -> str:
        filter = SanitizingFilter(sensitive_strings)
        record = LogRecord("", INFO, ".", 0, msg, args=args, exc_info=None)
        filter.filter(record)
        return record.getMessage()

    def test_sanitize(self):
        self.assertEqual("**c", self.sanitize({"a", "b"}, "abc"))

    def test_sanitize_with_string_arguments(self):
        self.assertEqual("**c**c*d", self.sanitize({"a", "b"}, "abc%s%s", "ab", "cbd"))

    def test_sanitize_with_mixed_arguments(self):
        self.assertEqual("*bc*b-1", self.sanitize({"a", "123"}, "abc%s%d", "ab", 123))

    def is_sensitive(self, name: str, patterns: Optional[List[str]] = None) -> bool:
        config = {"patterns": patterns} if patterns else {}
        ext = LogSanititerExtension()
        ext.configure_extension(LOG_SANITIZER, True, config)
        return ext.is_sensitive(name)

    def test_is_sensitive(self):
        self.assertTrue(self.is_sensitive("XKEY"))
        self.assertFalse(self.is_sensitive("XMAGIC"))

    def test_is_sensitive_case_insensitive(self):
        self.assertTrue(self.is_sensitive("xkey"))
        self.assertFalse(self.is_sensitive("xmagic"))

    def test_is_sensitive_with_custom_patterns(self):
        patterns = ["*MAGIC*"]
        self.assertTrue(self.is_sensitive("XKEY", patterns))
        self.assertTrue(self.is_sensitive("XMAGIC", patterns))
        self.assertFalse(self.is_sensitive("XCODE", patterns))

    def extend_environment(self, env: Dict[str, str]) -> Set[str]:
        ext = LogSanititerExtension()
        ext.extend_environment("", env)
        return ext.sensitive_strings

    def test_extend_environment(self):
        self.assertEqual(
            {"abc"}, self.extend_environment({"XKEY": "abc", "XMAGIC": "123"})
        )
