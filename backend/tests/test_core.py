import logging

import httpx
import pytest
import respx
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import override_settings
from django.urls import path
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.test import APIClient
from rest_framework.views import APIView

from core import http
from core.errors import ApiError, UpstreamError
from core.http import request_json

URL = "https://weather.test/forecast"


class UpstreamFailureView(APIView):
    def get(self, request):
        raise UpstreamError("weather")


class ApiErrorView(APIView):
    def get(self, request):
        raise ApiError("trip.invalid_stop", "Stop is outside the route", status=422)


class ValidationView(APIView):
    def get(self, request):
        raise ValidationError({"origin": ["This field is required."]})


class ThrottledView(APIView):
    def get(self, request):
        raise Throttled(wait=30)


class MissingView(APIView):
    def get(self, request):
        raise Http404("secret path")


class ForbiddenView(APIView):
    def get(self, request):
        raise PermissionDenied


class CrashView(APIView):
    def get(self, request):
        raise RuntimeError("secret internals")


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(http, "RETRY_DELAY_S", 0)


urlpatterns = [
    path("validation", ValidationView.as_view()),
    path("throttled", ThrottledView.as_view()),
    path("crash", CrashView.as_view()),
    path("missing", MissingView.as_view()),
    path("forbidden", ForbiddenView.as_view()),
    path("upstream", UpstreamFailureView.as_view()),
    path("api-error", ApiErrorView.as_view()),
]


@respx.mock
def test_retries_once_then_succeeds():
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    assert request_json("GET", URL, service="weather") == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_raises_upstream_error_after_retry():
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamError) as exc:
        request_json("GET", URL, service="weather")
    assert exc.value.service == "weather"
    assert route.call_count == 2


@respx.mock
def test_retries_on_timeout():
    route = respx.get(URL).mock(
        side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200, json=[1])]
    )
    assert request_json("GET", URL, service="weather") == [1]
    assert route.call_count == 2


@respx.mock
def test_does_not_retry_client_errors():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(UpstreamError):
        request_json("GET", URL, service="geocoder")
    assert route.call_count == 1


@override_settings(ROOT_URLCONF=__name__)
def test_upstream_error_renders_502_dotted_code():
    response = APIClient().get("/upstream")
    assert response.status_code == 502
    assert response.json() == {
        "code": "upstream.weather_unavailable",
        "detail": "The weather service is unavailable",
    }


@override_settings(ROOT_URLCONF=__name__)
def test_api_error_renders_code_and_status():
    response = APIClient().get("/api-error")
    assert response.status_code == 422
    assert response.json() == {
        "code": "trip.invalid_stop",
        "detail": "Stop is outside the route",
    }


def test_health():
    response = APIClient().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@respx.mock
def test_retries_on_connect_error():
    route = respx.get(URL).mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json={"ok": 1})]
    )
    assert request_json("GET", URL, service="weather") == {"ok": 1}
    assert route.call_count == 2


@respx.mock
def test_retries_on_429():
    route = respx.get(URL).mock(side_effect=[httpx.Response(429), httpx.Response(200, json=[])])
    assert request_json("GET", URL, service="weather") == []
    assert route.call_count == 2


@respx.mock
def test_invalid_json_raises_upstream_error():
    respx.get(URL).mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(UpstreamError) as exc:
        request_json("GET", URL, service="weather")
    assert exc.value.upstream_status == 200


@respx.mock
def test_upstream_error_exposes_status_and_body(caplog):
    respx.get(URL).mock(return_value=httpx.Response(400, text="no route found"))
    with caplog.at_level(logging.WARNING, logger="core.http"), pytest.raises(UpstreamError) as exc:
        request_json("GET", URL, service="routing")
    assert exc.value.upstream_status == 400
    assert exc.value.status_code == 502
    assert exc.value.upstream_body == "no route found"
    assert "routing returned HTTP 400" in caplog.text


@respx.mock
def test_upstream_error_chains_cause():
    respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(UpstreamError) as exc:
        request_json("GET", URL, service="weather")
    assert isinstance(exc.value.__cause__, httpx.ConnectError)


@override_settings(ROOT_URLCONF=__name__)
def test_validation_error_shape():
    response = APIClient().get("/validation")
    assert response.status_code == 400
    assert response.json() == {
        "code": "validation.invalid",
        "detail": "Invalid input.",
        "fields": {"origin": ["This field is required."]},
    }


@override_settings(ROOT_URLCONF=__name__)
def test_throttled_uses_api_prefix():
    response = APIClient().get("/throttled")
    assert response.status_code == 429
    assert response.json()["code"] == "api.throttled"
    assert response.json()["detail"] == "Request was throttled. Expected available in 30 seconds."
    assert response["Retry-After"] == "30"


@override_settings(ROOT_URLCONF=__name__)
def test_unhandled_exception_renders_generic_500():
    response = APIClient(raise_request_exception=False).get("/crash")
    assert response.status_code == 500
    assert response.json() == {"code": "server.error", "detail": "Something went wrong."}


@override_settings(ROOT_URLCONF=__name__)
def test_django_404_renders_not_found():
    response = APIClient().get("/missing")
    assert response.status_code == 404
    assert response.json() == {"code": "api.not_found", "detail": "Not found."}


@override_settings(ROOT_URLCONF=__name__)
def test_django_permission_denied_renders_permission_denied():
    response = APIClient().get("/forbidden")
    assert response.status_code == 403
    assert response.json() == {
        "code": "api.permission_denied",
        "detail": "You do not have permission to perform this action.",
    }
