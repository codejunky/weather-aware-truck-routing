from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from trips.mappers import TripPlanMapper
from trips.serializers import TripPlanRequestSerializer
from trips.services import plan_trip


class TripPlanView(APIView):
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "plan"

    def post(self, request):
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(TripPlanMapper.to_response(plan_trip(serializer.to_request())))
