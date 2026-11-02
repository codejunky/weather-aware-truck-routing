from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.errors import ApiError
from providers import geocoding

MIN_QUERY = 3
MAX_QUERY = 120


class GeocodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "geocode"

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not MIN_QUERY <= len(q) <= MAX_QUERY:
            raise ApiError(
                "validation.query_length",
                f"Query must be {MIN_QUERY}-{MAX_QUERY} characters.",
            )
        return Response({"results": geocoding.search(q)})
