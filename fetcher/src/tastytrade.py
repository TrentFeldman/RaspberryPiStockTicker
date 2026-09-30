"""A small, logged-in tastytrade API client.

How tastytrade login works (OAuth):
  1. The long-lived refresh token + client secret (tastytrade.conf) are
     exchanged at /oauth/token for an ACCESS token that lasts 15 minutes.
  2. Every other request carries that access token.
  3. Shortly before it expires, a new one is fetched (step 1 again).

The client does this by itself: callers just call get(path). The access
token and the account number are registered with SecretFilter, so they're
never readable in the log.

Only read-only endpoints are used: sessions, instruments, market data,
balances, net-liq history. The OAuth grant should have the read scope only.
"""

from __future__ import annotations

import time
import urllib.parse

from . import web
from .config import Config
from .credentials import Credentials
from .logs import SecretFilter, log
from .web import ApiError, AuthError

SYMBOLS_PER_REQUEST = 100  # tastytrade's cap on symbols per market-data/instruments request


class TastyClient:
    """tastytrade REST client with automatic access-token refresh."""

    TOKEN_LIFETIME = 15 * 60  # seconds an access token is valid
    REFRESH_MARGIN = 2 * 60   # renew this long before it runs out

    def __init__(self, cfg: Config, creds: Credentials):
        self.cfg, self.creds = cfg, creds
        self.token: str | None = None  # current access token (None = not logged in yet)
        self.token_time = 0.0          # when it was issued (epoch)
        self.account_number: str | None = None

    def token_age(self) -> float | None:
        """Seconds since the access token was issued (None if there is none)."""
        return time.time() - self.token_time if self.token else None

    def refresh_token(self) -> None:
        """Log in: exchange the refresh token for a fresh 15-minute access token.

        A rejection (400/401/403) raises AuthError, which makes the app pause
        ALL tastytrade calls for 30 minutes (see app.py) so a bad secret can't
        turn into repeated failed logins and an IP block.
        """
        try:
            data = web.http_json("POST", self.cfg.base_url + "/oauth/token", timeout=self.cfg.timeout,
                                 body={"grant_type": "refresh_token",
                                       "refresh_token": self.creds.refresh_token,
                                       "client_secret": self.creds.client_secret})
        except ApiError as e:
            if e.status in (400, 401, 403):
                raise AuthError(e.status, e.code, e.message) from None
            raise
        token = data.get("access_token")
        if not token:
            raise AuthError(200, "no_token", "token response had no access_token")
        self.token, self.token_time = token, time.time()
        SecretFilter.add(token)
        log.debug("access token refreshed (expires_in=%s)", data.get("expires_in"))

    def get(self, path: str, params: list[tuple[str, str]] | None = None) -> dict:
        """GET an API path, logged in. Logs in first when the token is missing
        or nearly expired; after a 401 (token rejected) logs in once more
        and retries once.

        params are (name, value) pairs, because tastytrade repeats names for
        lists: [("symbol[]", "AAPL"), ("symbol[]", "MSFT")].
        """
        if not self.token or time.time() - self.token_time > self.TOKEN_LIFETIME - self.REFRESH_MARGIN:
            self.refresh_token()
        url = self.cfg.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in (1, 2):
            try:
                return web.http_json("GET", url, timeout=self.cfg.timeout,
                                     headers={"Authorization": f"Bearer {self.token}"})
            except ApiError as e:
                if e.status == 401 and attempt == 1:
                    log.info("got 401 (%s); refreshing access token once", e.code)
                    self.refresh_token()
                    continue
                raise
        raise AssertionError("unreachable")

    def get_items(self, path: str, params: list[tuple[str, str]]) -> list[dict]:
        """GET a symbol-list endpoint, 100 symbols per request (tastytrade's
        limit), and return all the items together.

        250 symbols -> 3 requests (100 + 100 + 50).
        """
        items: list[dict] = []
        for i in range(0, len(params), SYMBOLS_PER_REQUEST):
            items += self.get(path, params[i:i + SYMBOLS_PER_REQUEST])["data"]["items"]
        return items

    def account(self) -> str:
        """The first open account number (looked up once, then remembered).
        Only its last two digits ever appear in the log."""
        if not self.account_number:
            items = self.get("/customers/me/accounts")["data"]["items"]
            open_accounts = [i["account"]["account-number"] for i in items
                             if not i["account"].get("is-closed")]
            if not open_accounts:
                raise ApiError(200, "no_account", "no open accounts on this login")
            if len(open_accounts) > 1:
                log.warning("%d accounts found; showing the first (****%s)", len(open_accounts),
                            open_accounts[0][-2:])
            self.account_number = open_accounts[0]
            SecretFilter.add(self.account_number)
        return self.account_number
