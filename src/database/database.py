"""Microsoft Graph connection -- a Singleton that owns the access token."""

import threading
import time

import requests
from requests.exceptions import HTTPError

from src.settings.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
_TOKEN_REFRESH_MARGIN_SECONDS = 300


class GraphDatabase:
    """Single shared Graph client: acquires and caches the Azure AD token
    (client-credentials flow) and sends authorised requests."""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._token = None
                instance._token_expiry = 0
                instance._token_lock = threading.Lock()
                cls._instance = instance
        return cls._instance

    def get_token(self):
        with self._token_lock:
            if self._token and time.time() < self._token_expiry - _TOKEN_REFRESH_MARGIN_SECONDS:
                return self._token
            url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
            response = requests.post(url, data={
                "grant_type": "client_credentials",
                "client_id": settings.azure_client_id,
                "client_secret": settings.azure_client_secret,
                "scope": "https://graph.microsoft.com/.default",
            })
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._token_expiry = time.time() + payload.get("expires_in", 3599)
            return self._token

    def request(self, method, endpoint, **kwargs):
        """Send an authorised request; raise RuntimeError with the Graph response on failure."""
        url = f"{GRAPH_BASE_URL}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.get_token()}", **kwargs.pop("headers", {})}
        response = requests.request(method, url, headers=headers, **kwargs)
        try:
            response.raise_for_status()
        except HTTPError:
            logger.error("Graph %s %s failed: %s %s", method, url, response.status_code, response.text)
            raise RuntimeError(
                f"\nGRAPH {method} FAILED\nURL: {url}\nStatus: {response.status_code}\nResponse: {response.text}\n"
            )
        return response.json() if response.text.strip() else {}


def get_database():
    return GraphDatabase()
