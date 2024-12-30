import gzip
import json
import zlib
from datetime import timedelta
from typing import Optional
from unittest.mock import MagicMock, call

import brotli
import pytest
import zstandard
from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpResponse
from django_redis import get_redis_connection
from redis.lock import Lock
from rest_framework.test import APIRequestFactory

import capyc.pytest as capy
from capyc.django.cache import delete_cache, reset_cache, settings
from capyc.django.serializer import Serializer


@pytest.fixture(autouse=True)
def setup(db, monkeypatch):

    monkeypatch.setattr(cache, "delete_pattern", MagicMock())
    yield


class ContentTypeSerializer(Serializer):
    model = ContentType
    path = "/contenttype"
    fields = {
        "default": ("id", "app_label"),
    }
    filters = ("app_label",)
    depth = 2
    ttl = 2


# duplicate
class PermissionSerializerDuplicate(Serializer):
    model = Permission
    path = "/permission"
    fields = {
        "default": ("id", "name"),
        "extra": ("codename", "content_type"),
        "ids": ("content_type", "groups"),
        "lists": ("groups",),
        "expand_ids": ("content_type[]",),
        "expand_lists": ("groups[]",),
    }
    rewrites = {
        "group_set": "groups",
    }
    filters = ("name", "codename", "content_type", "groups")
    depth = 2
    # content_type = (ContentTypeSerializer, 'group')
    content_type = ContentTypeSerializer


class GroupSerializer(Serializer):
    model = Group
    path = "/group"
    fields = {
        "default": ("id", "name"),
        "lists": ("permissions",),
        "expand_lists": ("permissions[]",),
    }
    filters = ("name", "permissions")
    depth = 2

    permissions = PermissionSerializerDuplicate


class PermissionSerializer(Serializer):
    model = Permission
    path = "/permission"
    fields = {
        "default": ("id", "name"),
        "extra": ("codename",),
        "ids": ("content_type",),
        "lists": ("groups",),
        "expand_ids": ("content_type[]",),
        "expand_lists": ("groups[]",),
    }
    rewrites = {
        "group_set": "groups",
    }
    filters = ("name", "codename", "content_type", "groups")
    depth = 2
    content_type = ContentTypeSerializer
    groups = GroupSerializer


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_permission(database: capy.Database):
    await database.acreate(permission=1, content_type=1)
    await delete_cache("auth.Permission")

    assert cache.delete_pattern.call_args_list == [
        call("tests.django.test_cache.PermissionSerializerDuplicate*"),
        call("tests.django.test_cache.GroupSerializer*"),
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_content_type(database: capy.Database):
    await database.acreate(content_type=1)
    await delete_cache("contenttypes.ContentType")

    assert cache.delete_pattern.call_args_list == [
        call("tests.django.test_cache.ContentTypeSerializer*"),
        call("tests.django.test_cache.PermissionSerializerDuplicate*"),
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_group(database: capy.Database):
    await database.acreate(group=1)
    await delete_cache("auth.Group")

    assert cache.delete_pattern.call_args_list == [
        call("tests.django.test_cache.GroupSerializer*"),
    ]
