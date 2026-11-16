"""Centralized logger: one structured format for every module."""

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_configured = False


def _configure_root(level):
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    _configured = True


def get_logger(name):
    from src.settings.settings import settings

    _configure_root(settings.log_level.upper())
    return logging.getLogger(name)
