"""Tests for src/web.py: every shape of API error becomes a short, readable ApiError."""

import unittest

import helpers  # noqa: F401  (sets up the import path)
from src.web import ApiError, parse_error_body


class ErrorTests(unittest.TestCase):
    def test_error_body_json(self):
        e = parse_error_body(401, b'{"error":{"code":"unauthorized","message":"expired"}}')
        self.assertEqual((e.status, e.code, e.message), (401, "unauthorized", "expired"))
        self.assertFalse(e.retryable)

    def test_error_body_oauth(self):
        e = parse_error_body(400, b'{"error":"invalid_grant","error_description":"bad token"}')
        self.assertEqual((e.code, e.message), ("invalid_grant", "bad token"))

    def test_error_body_oauth_actual(self):
        # What /oauth/token really returned for a wrong client secret (2026-09-26).
        e = parse_error_body(400, b'{"error_code":"invalid_grant","error_description":"Client secret mismatch"}')
        self.assertEqual((e.code, e.message), ("invalid_grant", "Client secret mismatch"))
        self.assertEqual(e.panel(), "400 invalid_grant")

    def test_panel_text(self):
        self.assertEqual(ApiError(None, "unreachable", "Name or service not known").panel(), "no network")
        self.assertEqual(ApiError(503, "html", "503 Service Unavailable").panel(), "HTTP 503")

    def test_error_body_html(self):
        e = parse_error_body(404, b"<html>\r\n<head><title>404 Not Found</title></head><body>nginx</body>")
        self.assertEqual((e.code, e.message), ("html", "404 Not Found"))

    def test_retryable(self):
        self.assertTrue(ApiError(None, "unreachable", "x").retryable)
        self.assertTrue(ApiError(429, "rate", "x").retryable)
        self.assertTrue(ApiError(503, "down", "x").retryable)
        self.assertFalse(ApiError(404, "nf", "x").retryable)


if __name__ == "__main__":
    unittest.main()
