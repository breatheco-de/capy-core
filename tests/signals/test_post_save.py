from unittest.mock import AsyncMock, call

import pytest

import capyc.pytest as capy
from capyc.django import cache


@pytest.fixture(autouse=True)
def setup(db, monkeypatch):

    monkeypatch.setattr(cache, "delete_cache", AsyncMock())
    yield


class TestCreate:
    @pytest.mark.asyncio
    @pytest.mark.django_db(reset_sequences=True)
    async def test_permission(self, database: capy.Database, signals: capy.Signals):
        signals.enable("django.db.models.signals.post_save")

        await database.acreate(permission=1, content_type=1)

        assert cache.delete_cache.call_args_list == [
            call("contenttypes.ContentType"),
            call("auth.Permission"),
        ]

    @pytest.mark.asyncio
    @pytest.mark.django_db(reset_sequences=True)
    async def test_content_type(self, database: capy.Database, signals: capy.Signals):
        signals.enable("django.db.models.signals.post_save")

        await database.acreate(content_type=1)

        assert cache.delete_cache.call_args_list == [
            call("contenttypes.ContentType"),
        ]

    @pytest.mark.asyncio
    @pytest.mark.django_db(reset_sequences=True)
    async def test_group(self, database: capy.Database, signals: capy.Signals):
        signals.enable("django.db.models.signals.post_save")

        await database.acreate(group=1)

        assert cache.delete_cache.call_args_list == [
            call("auth.Group"),
        ]


class TestUpdate:
    @pytest.mark.asyncio
    @pytest.mark.django_db(reset_sequences=True)
    async def test_permission(self, database: capy.Database, signals: capy.Signals):
        signals.enable("django.db.models.signals.post_save")

        model = await database.acreate(permission=1, content_type=1)
        cache.delete_cache.call_args_list = []

        model.permission.name = "test"
        model.permission.codename = "test"
        await model.permission.asave()

        assert cache.delete_cache.call_args_list == [
            call("auth.Permission"),
        ]

    @pytest.mark.asyncio
    @pytest.mark.django_db(reset_sequences=True)
    async def test_content_type(self, database: capy.Database, signals: capy.Signals):
        signals.enable("django.db.models.signals.post_save")

        model = await database.acreate(content_type=1)
        cache.delete_cache.call_args_list = []

        model.content_type.app_label = "test"
        await model.content_type.asave()

        assert cache.delete_cache.call_args_list == [
            call("contenttypes.ContentType"),
        ]

    @pytest.mark.asyncio
    @pytest.mark.django_db(reset_sequences=True)
    async def test_group(self, database: capy.Database, signals: capy.Signals):
        signals.enable("django.db.models.signals.post_save")

        model = await database.acreate(group=1)
        cache.delete_cache.call_args_list = []

        model.group.name = "test"
        await model.group.asave()

        assert cache.delete_cache.call_args_list == [
            call("auth.Group"),
        ]
