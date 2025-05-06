"""Class to handle Plaid API calls."""

import logging
import os
from typing import Any, Self

import httpx
from config import Config

from exceptions import Plaid2FireflyConnectionError, Plaid2FireflyError, Plaid2FireflyTimeoutError

_LOGGER = logging.getLogger(__name__)

class PlaidClient:
    """Plaid client for making API calls"""

    def __init__(self, plaid_client_id: str, plaid_secret: str, plaid_env: str, request_timeout: float = 10.0):
        """Initialize the Plaid client"""
        self.plaid_client_id: str = plaid_client_id
        self.plaid_secret: str = plaid_secret
        self.plaid_env: str = plaid_env
        self.public_token: str | None = None
        
        
        self._config = Config()       
        self._request_timeout = request_timeout
        self._client: httpx.AsyncClient | None = None

    async def _request(
        self,
        uri: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make a request to the Plaid API"""
        url = f"https://{self.plaid_env}.plaid.com{uri}"

        headers = {
            "Accept": "application/json, text/plain",
            "User-Agent": "Plaid2Firefly",
        }

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._request_timeout)

        # Sanitize params and json by removing None values
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        if json:
            json = {k: v for k, v in json.items() if v is not None}

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params if method == "GET" else None,
                json=json if method == "POST" else None,
            )
            response.raise_for_status()
        except httpx.RequestError as err:
            msg = f"Request error during {method} {url}: {err}"
            raise Plaid2FireflyConnectionError(msg) from err
        except httpx.HTTPStatusError as err:
            msg = f"HTTP status error during {method} {url}: {err.response.status_code}, {err.response.text}"
            raise Plaid2FireflyConnectionError(msg) from err

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            msg = "Unexpected content type response from the Plaid API"
            raise Plaid2FireflyError(
                msg,
                {"Content-Type": content_type, "response": response.text},
            )

        return response.json()

    async def create_public_token(self) -> str | None:
        """Get the public token from the Plaid client"""
        _LOGGER.info("Creating public token")

        # Ensure country_codes is a list of strings
        country_codes = self._config.get("country_codes", [])
        if not isinstance(country_codes, list) or not all(isinstance(code, str) for code in country_codes):
            raise Plaid2FireflyConnectionError("country_codes must be an array of strings")

        msg = {
            "client_id": self.plaid_client_id,
            "secret": self.plaid_secret,
            "client_name": "Plaid2Firefly",
            "country_codes": country_codes,
            "language": "en",
            "user": {"client_user_id": "Plaid2Firefly"},
            "products": ["auth", "transactions", "liabilities"],
        }

        _LOGGER.debug("Creating public token with message: %s", msg)

        public_token = await self._request(uri="/link/token/create", method="POST", json=msg)

        _LOGGER.info("Fetched token information: %s", public_token)
        self.public_token = public_token.get("link_token")
        return self.public_token

    async def close(self) -> None:
        """Close the HTTPX client session."""
        if self._client:
            await self._client.aclose()
            _LOGGER.info("Closed HTTPX client session")

    async def __aenter__(self) -> Self:
        """Async enter."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._request_timeout)
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit."""
        await self.close()