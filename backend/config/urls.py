from django.urls import include, path

from core.views import health

api_urlpatterns = [
    path("health", health),
]

urlpatterns = [
    path("api/", include(api_urlpatterns)),
]
