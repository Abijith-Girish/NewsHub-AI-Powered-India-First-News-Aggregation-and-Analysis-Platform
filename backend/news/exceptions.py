"""API error handling that never leaks internals to the client."""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("newshub")


class ProviderUnavailable(Exception):
    """Raised when every configured external news provider failed."""


class AIServiceError(Exception):
    """Raised when summary/fact-check generation cannot be completed."""


def newshub_exception_handler(exc, context):
    handler = context.get("view").__class__.__name__ if context.get("view") else "unknown"

    if isinstance(exc, ProviderUnavailable):
        logger.warning("Provider unavailable in %s: %s", handler, exc)
        return Response(
            {
                "detail": str(exc)
                or "News providers are temporarily unavailable. Please try again.",
                "code": "provider_unavailable",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if isinstance(exc, AIServiceError):
        logger.warning("AI service error in %s: %s", handler, exc)
        return Response(
            {
                "detail": str(exc) or "The AI service could not complete this request.",
                "code": "ai_unavailable",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    response = exception_handler(exc, context)
    if response is not None:
        return response

    logger.exception("Unhandled API error in %s", handler)
    return Response(
        {"detail": "Something went wrong on our side. Please try again.", "code": "server_error"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
