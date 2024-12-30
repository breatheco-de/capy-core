import logging
from typing import Any, Type

from asgiref.sync import async_to_sync
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

import capyc.django.cache as actions

__all__ = []

logger = logging.getLogger(__name__)


@receiver(post_save)
def on_save(*args: Any, **kwargs: Any):
    clean_cache(*args, **kwargs)


@receiver(post_delete)
def on_delete(*args: Any, **kwargs: Any):
    clean_cache(*args, **kwargs)


@async_to_sync
async def clean_cache(sender: Type[models.Model], **_: Any):
    key = f"{sender._meta.app_label}.{sender.__name__}"
    await actions.delete_cache(key)
