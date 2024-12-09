from django.apps import AppConfig


class CapyCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "capyc"

    def ready(self):
        from . import receivers  # noqa: F401
