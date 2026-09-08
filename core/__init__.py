"""
core/__init__.py

Initializes the core package for the HR-Agent-Microsoft.
Exposes the primary Microsoft Graph API authentication and request functions.
"""

from .graph_auth import get_graph_token
from .graph_api import graph_get, graph_post, graph_put

__all__ = [
    "get_graph_token",
    "graph_get",
    "graph_post",
    "graph_put"
]