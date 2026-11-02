import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class ApiError(APIException):
    def __init__(self, code: str, detail: str, status: int = 400):
        super().__init__(detail, code)
        self.status_code = status


class UpstreamError(ApiError):
    def __init__(self, service: str, status_code: int | None = None, body: str | None = None):
        super().__init__(
            f"upstream.{service}_unavailable",
            f"The {service} service is unavailable",
            status.HTTP_502_BAD_GATEWAY,
        )
        self.service = service
        self.upstream_status = status_code
        self.upstream_body = body


def exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied()
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error", exc_info=exc)
        return Response(
            {"code": "server.error", "detail": "Something went wrong."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(exc, ValidationError):
        fields = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        return Response(
            {
                "code": "validation.invalid",
                "detail": "Invalid input.",
                "fields": {k: [str(m) for m in _as_list(v)] for k, v in fields.items()},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, ApiError):
        return Response(
            {"code": exc.get_codes(), "detail": str(exc.detail)}, status=exc.status_code
        )
    return Response(
        {"code": f"api.{exc.get_codes()}", "detail": str(exc.detail)},
        status=response.status_code,
        headers=dict(response.headers),
    )


def _as_list(value):
    return value if isinstance(value, list) else [value]
