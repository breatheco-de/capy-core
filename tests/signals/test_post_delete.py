from unittest.mock import AsyncMock, call

import pytest

import capyc.pytest as capy
from capyc.django import cache


@pytest.fixture(autouse=True)
def setup(db, monkeypatch):

    monkeypatch.setattr(cache, "delete_cache", AsyncMock())
    yield


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_permission(database: capy.Database, signals: capy.Signals):
    signals.enable("django.db.models.signals.post_delete")

    model = await database.acreate(permission=1, content_type=1)
    await model.permission.adelete()

    assert cache.delete_cache.call_args_list == [
        call("auth.Permission"),
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_content_type(database: capy.Database, signals: capy.Signals):
    signals.enable("django.db.models.signals.post_delete")

    model = await database.acreate(content_type=1)
    await model.content_type.adelete()

    assert cache.delete_cache.call_args_list == [
        call("contenttypes.ContentType"),
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_group(database: capy.Database, signals: capy.Signals):
    signals.enable("django.db.models.signals.post_delete")

    model = await database.acreate(group=1)
    await model.group.adelete()

    assert cache.delete_cache.call_args_list == [
        call("auth.Group"),
    ]
