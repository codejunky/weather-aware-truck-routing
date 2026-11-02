from django.urls import path

from trips.views import TripPlanView

urlpatterns = [path("trips/plan", TripPlanView.as_view())]
