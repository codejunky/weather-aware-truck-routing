from django.urls import include, path

from core.views import health

api_urlpatterns = [
    path("health", health),
    path("", include("geocoding.urls")),
    path("", include("trips.urls")),
]

urlpatterns = [
    path("api/", include(api_urlpatterns)),
]
