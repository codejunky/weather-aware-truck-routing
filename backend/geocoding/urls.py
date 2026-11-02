from django.urls import path

from geocoding.views import GeocodeView

urlpatterns = [path("geocode", GeocodeView.as_view())]
