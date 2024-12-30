from django.urls import path

from .views import delete_cache

app_name = "admissions"
urlpatterns = [
    path("cache/delete", delete_cache, name="cache_delete"),
]
