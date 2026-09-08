"""
core/graph_auth.py

Handles Azure AD Client Credentials flow using MSAL.
"""
import os
import msal
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
TENANT_ID = os.getenv("AZURE_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# The .default scope triggers the Application permissions granted in the Azure portal
SCOPES = ["https://graph.microsoft.com/.default"]

def get_graph_token() -> str:
    """
    Acquires a valid access token from Entra ID (Azure AD).
    MSAL automatically handles token caching and refreshing.
    """
    # Guard clause to catch missing environment variables early
    if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
        raise ValueError(
            "CRITICAL ERROR: Missing Azure AD credentials. "
            "Ensure AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_TENANT_ID "
            "are properly set in your .env file."
        )

    # Initialize the MSAL Confidential Client
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY
    )

    # 1. Try to find a valid token in the local cache first
    result = app.acquire_token_silent(SCOPES, account=None)

    # 2. If no valid token exists in cache, execute the network request to Azure AD
    if not result:
        result = app.acquire_token_for_client(scopes=SCOPES)

    if "access_token" in result:
        return result["access_token"]
    else:
        error_msg = result.get("error", "Unknown error")
        error_desc = result.get("error_description", "No description provided.")
        raise RuntimeError(f"Failed to acquire MS Graph token: {error_msg} - {error_desc}")