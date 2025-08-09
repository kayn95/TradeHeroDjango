# trades/apps.py
from django.apps import AppConfig

class TradesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trades"

    def ready(self):
        # Import “late” pour que Django charge les receivers
        from . import signals  # noqa: F401
