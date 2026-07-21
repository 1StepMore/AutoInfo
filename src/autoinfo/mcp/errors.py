"""Standardised error types and helpers for MCP tool responses.

Provides ``ErrorCode`` enum for consistent error classification,
``ErrorResponse`` TypedDict for type-safe error dicts, and helper
functions to build error responses in the shape expected by agents.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, TypedDict

from mcp.types import TextContent


class ErrorCode(str, Enum):
    """Error codes for MCP tool responses.

    Each member maps to a string value used as the ``error_code`` field
    in error dicts.  Unknown/unexpected exceptions map to ``INTERNAL_ERROR``.
    """

    NOT_FOUND = "NotFound"
    DOMAIN_NOT_FOUND = "DomainNotFound"
    VALIDATION_ERROR = "ValidationError"
    INVALID_SOURCE_ID = "InvalidSourceId"
    SOURCE_NOT_FOUND = "SourceNotFound"
    TIMEOUT = "Timeout"
    TOPIC_NOT_FOUND = "TopicNotFound"
    KEYWORD_NOT_FOUND = "KeywordNotFound"
    EMAIL_NOT_ENABLED = "EmailNotEnabled"
    EMAIL_SEND_FAILED = "EmailSendFailed"
    INVALID_CRON_EXPRESSION = "InvalidCronExpression"
    SCHEDULE_ALREADY_EXISTS = "ScheduleAlreadyExists"
    SCHEDULE_NOT_FOUND = "ScheduleNotFound"
    NOT_PUBLISHED = "NotPublished"
    COLLECTION_FAILED = "CollectionFailed"
    PROCESSING_FAILED = "ProcessingFailed"
    INVALID_SECTION = "InvalidSection"
    UNKNOWN_TOOL = "UnknownTool"
    INTERNAL_ERROR = "InternalError"


class ErrorResponse(TypedDict):
    """Shape of a standardised error response dict.

    Fields mirror the dict returned by :func:`error_dict` and match
    the existing pattern in ``server.py``.
    """

    error_code: ErrorCode
    message: str
    actionable: bool


def error_dict(
    error_code: ErrorCode,
    message: str = "",
    actionable: bool = True,
) -> dict[str, Any]:
    """Build a standardised error dict.

    Returns a dict with ``error_code`` (the enum *value* string),
    ``message``, and ``actionable`` — the same shape used throughout
    the MCP server.
    """
    return {
        "error_code": error_code.value,
        "message": message,
        "actionable": actionable,
    }


def error_response(
    error_code: ErrorCode,
    message: str = "",
    actionable: bool = True,
) -> list[TextContent]:
    """Build a standardised MCP error response.

    Returns ``list[TextContent]`` containing a single JSON-serialised
    error dict — the format MCP tools return when they encounter an
    error they want the agent to handle.
    """
    return [
        TextContent(
            type="text",
            text=json.dumps({
                "error_code": error_code.value,
                "message": message,
                "actionable": actionable,
            }),
        ),
    ]
