"""
PolicyIQ — Analytics Logger
Structured request/response logging middleware.
"""

import time
import uuid
from datetime import datetime
from typing import Callable, Optional

import structlog

logger = structlog.get_logger(__name__)


def get_request_logger(request_id: str, session_id: str):
    return logger.bind(request_id=request_id, session_id=session_id)
