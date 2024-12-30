from typing import Generator

import pytest
from asgiref.sync import async_to_sync

from capyc.django.cache import reset_cache

__all__ = ["clean_cache"]


@async_to_sync
async def x_reset_cache():
    await reset_cache()


@pytest.fixture(autouse=True, scope="function")
def clean_cache() -> Generator[None, None, None]:
    x_reset_cache()
    yield
