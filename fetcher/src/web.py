"""HTTP: every request the fetcher makes goes through http_json() below.

That gives one place for the rules every call follows:
  * JSON in, JSON out, with a timeout
  * a User-Agent "hub75-ticker/1.0" (tastytrade rejects requests without
    a product/version User-Agent)
  * ANY failure becomes an ApiError with a short, readable reason, never
    a raw urllib exception. Callers only ever need `except ApiError`.

The unit tests swap http_json for a fake, so the other files call it as
`web.http_json(...)` (through the module) instead of importing the function
directly; that way the swap reaches every caller.

Error examples, as they appear in the log and on the panel:

    network unreachable: [Errno -2] Name or service not known  ->  "no network"
    HTTP 503 html: 503 Service Unavailable                      ->  "HTTP 503"
    HTTP 400 invalid_grant: Client secret mismatch              ->  "400 invalid_grant"
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import VERSION

USER_AGENT = f"hub75-ticker/{VERSION}"  # tastytrade requires product/version


class ApiError(Exception):
    """An API call failed.

    status    HTTP status (401, 503, ...), or None when the server was never
              reached (no network, timeout, bad JSON)
    code      short machine-ish reason ("invalid_grant", "unreachable", "html")
    message   human-readable detail
    """

    def __init__(self, status: int | None, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(self.short())

    @property
    def retryable(self) -> bool:
        """True if trying again soon might work: network trouble, rate
        limiting (429) or a server-side error (5xx). A 400/404 won't fix itself."""
        return self.status is None or self.status == 429 or self.status >= 500

    def short(self) -> str:
        """One line for the log, at most 160 characters."""
        where = f"HTTP {self.status}" if self.status else "network"
        return f"{where} {self.code}: {self.message}"[:160]

    def panel(self) -> str:
        """Very short form for the LED panel. The panel fits ~23 characters
        including a label like "AUTH " or "SESSIONS ", so keep this <= 18."""
        if self.status is None:
            return "no network" if self.code == "unreachable" else self.code[:18]
        if self.code in ("html", "unknown", "error"):
            return f"HTTP {self.status}"
        return f"{self.status} {self.code}"[:18]


class AuthError(ApiError):
    """The refresh token / client secret was rejected. Do NOT retry quickly:
    tastytrade blocks an IP for ~8 hours after repeated failed logins."""


def parse_error_body(status: int | None, body: bytes) -> ApiError:
    """Turn an error response into an ApiError.

    tastytrade answers errors in one of three shapes:
      {"error": {"code": ..., "message": ...}}           normal API errors
      {"error_code": ..., "error_description": ...}      /oauth/token
      an nginx HTML page                                 bad path, bad User-Agent
    """
    text = body.decode("utf-8", "replace")
    try:
        data = json.loads(text)
        err = data.get("error", {})
        if isinstance(err, dict) and (err.get("code") or err.get("message")):
            return ApiError(status, str(err.get("code", "error")), str(err.get("message", "")))
        # OAuth-style: {"error": "invalid_grant", ...} per RFC 6749, or what
        # /oauth/token actually returns: {"error_code": ..., "error_description": ...}
        code = err if isinstance(err, str) and err else data.get("error_code")
        if code:
            return ApiError(status, str(code), str(data.get("error_description", "")))
    except (ValueError, AttributeError):
        pass  # not JSON (or not a JSON object): try HTML below
    if "<title>" in text:
        title = text.split("<title>", 1)[1].split("</title>", 1)[0].strip()
        return ApiError(status, "html", title)
    return ApiError(status, "unknown", " ".join(text.split())[:100])


def http_json(method: str, url: str, *, headers: dict | None = None, body: dict | None = None,
              timeout: float = 15) -> dict:
    """One HTTP request returning the parsed JSON reply; raises ApiError on
    any failure (HTTP error, no network, timeout, reply isn't JSON)."""
    h = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # the server answered with an error status
        raise parse_error_body(e.code, e.read()) from None
    except urllib.error.URLError as e:   # never reached the server (DNS, refused, ...)
        raise ApiError(None, "unreachable", str(e.reason)) from None
    except (TimeoutError, ConnectionError, OSError) as e:
        raise ApiError(None, type(e).__name__, str(e)) from None
    except ValueError as e:              # the reply wasn't valid JSON
        raise ApiError(None, "bad_json", str(e)) from None
