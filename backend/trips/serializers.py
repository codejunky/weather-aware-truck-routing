from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from trips.services import TripRequest

SAMPLE_INTERVALS_MI = (10, 25, 50)
MAX_LOAD_LB = 80_000
MAX_LEAD = timedelta(days=7)
MAX_LAG = timedelta(hours=1)


class AwareDateTimeField(serializers.DateTimeField):
    default_error_messages = {
        "naive": "Include a UTC offset, e.g. 2026-11-02T08:00:00-06:00.",
    }

    def enforce_timezone(self, value):
        if timezone.is_naive(value):
            self.fail("naive")
        return value


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200, required=False, allow_blank=True)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class TripPlanRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_at = AwareDateTimeField()
    load_weight_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_LB)
    sample_interval_mi = serializers.ChoiceField(choices=SAMPLE_INTERVALS_MI, default=25)

    def validate_departure_at(self, value):
        now = timezone.now()
        if not now - MAX_LAG <= value <= now + MAX_LEAD:
            raise serializers.ValidationError(
                "Departure must be between 1 hour ago and 7 days from now."
            )
        return value

    def to_request(self) -> TripRequest:
        data = self.validated_data
        return TripRequest(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(data["destination"]["lat"], data["destination"]["lon"]),
            departure_at=data["departure_at"],
            load_lb=data["load_weight_lb"],
            interval_mi=data["sample_interval_mi"],
        )
