from logging import getLogger
from typing import Any, Type

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import delete_cache, settings

logger = getLogger(__name__)


def clean_cache(sender: Type[models.Model], **_: Any):
    if settings["is_cache_enabled"] is False:
        logger.debug("Cache has been disabled")
        return

    delete_cache(f"{sender._meta.app_label}.{sender.__name__}")


@receiver(post_save)
def on_save(*args: Any, **kwargs: Any):
    clean_cache(*args, **kwargs)


@receiver(post_delete)
def on_delete(*args: Any, **kwargs: Any):
    clean_cache(*args, **kwargs)
