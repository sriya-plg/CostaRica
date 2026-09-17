import logging
import time
from typing import Any

import httpx
import msal

from app.core.config import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["https://graph.microsoft.com/.default"]
MAX_RETRIES = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GraphClient:
    def __init__(self) -> None:
        self._app = msal.ConfidentialClientApplication(
            settings.CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.TENANT_ID}",
            client_credential=settings.CLIENT_SECRET,
        )
        self._token: str | None = None

    def _acquire_token(self) -> str:
        result = self._app.acquire_token_for_client(scopes=SCOPES)
        if "access_token" not in result:
            error = result.get("error_description") or result.get("error") or "unknown"
            raise RuntimeError(f"Failed to acquire Graph token: {error}")
        return result["access_token"]

    def _get_token(self) -> str:
        if self._token is None:
            self._token = self._acquire_token()
        return self._token

    def _refresh_token(self) -> None:
        self._token = self._acquire_token()

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{GRAPH_BASE}{path}"
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            headers = {
                "Authorization": f"Bearer {self._get_token()}",
                "Content-Type": "application/json",
            }
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.request(method, url, headers=headers, json=json)

                if response.status_code == 401 and attempt < MAX_RETRIES - 1:
                    logger.warning("Graph token expired, refreshing")
                    self._refresh_token()
                    continue

                if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES - 1:
                    delay = 2**attempt
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        delay = int(retry_after)
                    logger.warning(
                        "Transient Graph error %s on %s %s, retry in %ss",
                        response.status_code,
                        method,
                        path,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                if response.is_error:
                    logger.error(
                        "Graph API error %s on %s %s: %s",
                        response.status_code,
                        method,
                        path,
                        response.text,
                    )
                response.raise_for_status()
                if response.status_code == 204:
                    return {}
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if (
                    exc.response.status_code in RETRYABLE_STATUS
                    and attempt < MAX_RETRIES - 1
                ):
                    time.sleep(2**attempt)
                    continue
                raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("Graph request failed without a captured error")


graph_client = GraphClient()
