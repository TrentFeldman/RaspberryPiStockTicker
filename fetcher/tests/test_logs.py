"""Tests for src/logs.py: secrets never reach the log; repeated errors are collapsed."""

import logging
import unittest

import helpers  # noqa: F401  (sets up the import path)
from src.logs import ErrorTracker, SecretFilter


class LoggingTests(unittest.TestCase):
    def test_secret_redaction(self):
        SecretFilter.add("supersecretvalue123")
        rec = logging.LogRecord("t", logging.INFO, "", 0, "token=%s", ("supersecretvalue123",), None)
        SecretFilter().filter(rec)
        self.assertEqual(rec.getMessage(), "token=***")

    def test_error_tracker_collapses_repeats(self):
        tr = ErrorTracker("quotes", repeat_every=600)
        with self.assertLogs("fetcher", level="INFO") as cm:
            tr.error("HTTP 503 down", 0)
            for t in range(1, 100):
                tr.error("HTTP 503 down", t)        # suppressed
            tr.error("HTTP 503 down", 700)          # summary
            tr.ok(800)                              # recovery
        self.assertEqual(len(cm.output), 3)
        self.assertIn("still failing", cm.output[1])
        self.assertIn("recovered", cm.output[2])


if __name__ == "__main__":
    unittest.main()
