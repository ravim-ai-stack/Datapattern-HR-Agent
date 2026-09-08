"""
core/graph_api.py
Handles OAuth2 token generation and unified Microsoft Graph requests.
"""

import os
import time
import requests
from requests.exceptions import HTTPError
from dotenv import load_dotenv

# Global cache variables for the Graph token
_TOKEN_CACHE = None
_TOKEN_EXPIRY = 0


# ================================================================
# 1. GET MICROSOFT GRAPH ACCESS TOKEN (With Caching)
# ================================================================
def get_graph_token():
    global _TOKEN_CACHE, _TOKEN_EXPIRY
    
    # If we have a cached token and it is valid for at least another 5 minutes, use it
    if _TOKEN_CACHE and time.time() < (_TOKEN_EXPIRY - 300):
        return _TOKEN_CACHE

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default"
    }

    resp = requests.post(url, data=data)
    resp.raise_for_status()
    
    token_data = resp.json()
    
    # Cache the token and calculate its expiration time
    _TOKEN_CACHE = token_data["access_token"]
    _TOKEN_EXPIRY = time.time() + token_data.get("expires_in", 3599)

    return _TOKEN_CACHE


# ================================================================
# 2. UNIFIED GRAPH POST
# ================================================================
def graph_post(endpoint, json_data=None, data=None, content_type="application/json"):
    """
    A robust POST wrapper for Microsoft Graph.
    Handles:
        - Authorization
        - JSON or binary data
        - Detailed error reporting
    """
    token = get_graph_token()

    url = f"https://graph.microsoft.com/v1.0/{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type
    }

    try:
        # JSON post
        if json_data is not None:
            resp = requests.post(url, headers=headers, json=json_data)
        # raw bytes post (upload)
        else:
            resp = requests.post(url, headers=headers, data=data)

        resp.raise_for_status()
        return resp.json() if resp.text.strip() else {}

    except HTTPError as e:
        error_details = resp.text if "resp" in locals() else str(e)
        raise RuntimeError(
            f"\nGRAPH POST FAILED\n"
            f"URL: {url}\n"
            f"Status: {resp.status_code if 'resp' in locals() else 'N/A'}\n"
            f"Response: {error_details}\n"
        )


# ================================================================
# 3. UNIFIED GRAPH PUT (Used for SharePoint File Upload)
# ================================================================
def graph_put(endpoint, data=None, content_type="application/octet-stream"):
    """
    Handles PUT requests for uploading files to SharePoint Drive.
    """
    token = get_graph_token()

    url = f"https://graph.microsoft.com/v1.0/{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }

    try:
        resp = requests.put(url, headers=headers, data=data)
        resp.raise_for_status()
        return resp.json()

    except HTTPError as e:
        error_details = resp.text if "resp" in locals() else str(e)
        raise RuntimeError(
            f"\nGRAPH PUT FAILED\n"
            f"URL: {url}\n"
            f"Status: {resp.status_code if 'resp' in locals() else 'N/A'}\n"
            f"Response: {error_details}\n"
        )


# ================================================================
# 4. UNIFIED GRAPH GET
# ================================================================
def graph_get(endpoint, params=None):
    """
    A robust GET wrapper for Microsoft Graph.
    """
    token = get_graph_token()
    url = f"https://graph.microsoft.com/v1.0/{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
        
    except HTTPError as e:
        error_details = resp.text if "resp" in locals() else str(e)
        raise RuntimeError(
            f"\nGRAPH GET FAILED\n"
            f"URL: {url}\n"
            f"Status: {resp.status_code if 'resp' in locals() else 'N/A'}\n"
            f"Response: {error_details}\n"
        )