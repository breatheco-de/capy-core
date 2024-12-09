import gzip
import json
import zlib
from datetime import timedelta
from typing import Optional

import brotli
import pytest
import zstandard
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpResponse
from django_redis import get_redis_connection
from redis.lock import Lock
from rest_framework.test import APIRequestFactory

import capyc.pytest as capy
from capyc.django.cache import reset_cache, settings
from capyc.django.serializer import Serializer


@pytest.fixture(autouse=True, scope="function")
def setup(db):
    reset_cache()
    yield

    # client = get_redis_connection("default")
    # with Lock(client, f"capyc:test:serializers", timeout=60, blocking_timeout=60):
    #     # assert 0
    #     reset_cache()
    #     yield


@pytest.fixture
def overwrite_settings(monkeypatch: pytest.MonkeyPatch):

    def wrapper(key, value):

        monkeypatch.setitem(settings, key, value)
        settings["asdasd"] = 123

    yield wrapper


def compress(value: str, encoding: Optional[str] = None):
    value = json.dumps(value)

    if encoding == "gzip":
        return gzip.compress(value.encode("utf-8"))
    elif encoding == "br":
        return brotli.compress(value.encode("utf-8"))
    elif encoding == "deflate":
        return zlib.compress(value.encode("utf-8"))
    elif encoding == "zstd":
        return zstandard.compress(value.encode("utf-8"))

    return value


def decompress(value: dict, encoding: Optional[str] = None):
    if encoding == "gzip":
        value["content"] = gzip.decompress(value["content"]).decode("utf-8")
    elif encoding == "br":
        value["content"] = brotli.decompress(value["content"])
    elif encoding == "deflate":
        value["content"] = zlib.decompress(value["content"]).decode("utf-8")
    elif encoding == "zstd":
        value["content"] = zstandard.decompress(value["content"]).decode("utf-8")

    value["content"] = json.loads(value["content"])
    return value


def assert_response(response: HttpResponse, expected, status=200, encoding=None):
    assert response.status_code == status

    if encoding == "gzip":
        assert json.loads(gzip.decompress(response.content).decode("utf-8")) == expected
    elif encoding == "br":
        assert json.loads(brotli.decompress(response.content)) == expected
    elif encoding == "deflate":
        assert json.loads(zlib.decompress(response.content).decode("utf-8")) == expected
    elif encoding == "zstd":
        assert json.loads(zstandard.decompress(response.content).decode("utf-8")) == expected
    else:
        assert json.loads(response.content) == expected


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


# PermissionSerializer.groups = GroupSerializer()


class UserSerializer(Serializer):
    model = User
    path = "/user"
    fields = {
        "default": ("id", "username"),
        "intro": ("first_name", "last_name"),
        "lists": ("groups", "permissions"),
        "expand_lists": ("groups[]", "groups.permissions[]", "permissions[]"),
    }
    rewrites = {
        "user_permissions": "permissions",
    }
    filters = (
        "username",
        "first_name",
        "last_name",
        "email",
        "date_joined",
        "groups",
        "permissions",
    )
    depth = 2

    groups = GroupSerializer
    permissions = PermissionSerializer


# @pytest.fixture(autouse=True)
# def setup(db):
#     yield


class TestNoExpandGet:

    # select
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(1) as captured:
            assert_response(
                serializer.get(id=model.permission.id),
                {
                    "id": model.permission.id,
                    "name": model.permission.name,
                },
            )

    # selectm2m select
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,ids")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(1) as captured:
            assert_response(
                serializer.get(id=model.permission.id),
                {
                    "id": model.permission.id,
                    "name": model.permission.name,
                    "codename": model.permission.codename,
                    "content_type": model.permission.content_type.id,
                },
            )

    # selectm2m select
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,lists")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(2) as captured:
            assert_response(
                serializer.get(id=model.permission.id),
                {
                    "id": model.permission.id,
                    "name": model.permission.name,
                    "codename": model.permission.codename,
                    "groups": {
                        "count": 2,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                        "next": None,
                        "previous": None,
                        "results": [
                            1,
                            2,
                        ],
                    },
                },
            )


class TestNoExpandFilter:

    # countselect
    def test_permission__default__two_items(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(2) as captured:
            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__two_sets__two_items__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,ids")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(2) as captured:
            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "codename": model.permission[0].codename,
                            "content_type": model.permission[0].content_type.id,
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "codename": model.permission[1].codename,
                            "content_type": model.permission[1].content_type.id,
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselectm2m select * 2
    def test_permission__two_sets__two_items__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,lists")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(4) as captured:
            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "codename": model.permission[0].codename,
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                            "groups": {
                                "count": 2,
                                "next": None,
                                "previous": None,
                                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                                "results": [1, 2],
                            },
                        },
                        {
                            "codename": model.permission[1].codename,
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                            "groups": {
                                "count": 2,
                                "next": None,
                                "previous": None,
                                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                                "results": [1, 2],
                            },
                        },
                    ],
                },
            )


class TestExpandGet:
    # selectm2m select
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        with django_assert_num_queries(1) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.get(id=model.permission.id),
                {
                    "id": model.permission.id,
                    "name": model.permission.name,
                },
            )

    # select
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_ids")

        with django_assert_num_queries(1) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.get(id=model.permission.id),
                {
                    "id": model.permission.id,
                    "name": model.permission.name,
                    "content_type": {
                        "id": model.permission.content_type.id,
                        "app_label": model.permission.content_type.app_label,
                    },
                },
            )

    # selectm2m select
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_lists")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.get(id=model.permission.id),
                {
                    "id": model.permission.id,
                    "name": model.permission.name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                        "results": [
                            {
                                "id": model.group[0].id,
                                "name": model.group[0].name,
                            },
                            {
                                "id": model.group[1].id,
                                "name": model.group[1].name,
                            },
                        ],
                    },
                },
            )


class TestExpandFilter:
    # countselect
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_ids")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                            "content_type": {
                                "id": model.permission[0].content_type.id,
                                "app_label": model.permission[0].content_type.app_label,
                            },
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                            "content_type": {
                                "id": model.permission[1].content_type.id,
                                "app_label": model.permission[1].content_type.app_label,
                            },
                        },
                    ],
                },
            )

    # countselectm2m select * 2
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_lists")

        with django_assert_num_queries(4) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                            "groups": {
                                "count": 2,
                                "next": None,
                                "previous": None,
                                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                                "results": [
                                    {
                                        "id": model.group[0].id,
                                        "name": model.group[0].name,
                                    },
                                    {
                                        "id": model.group[1].id,
                                        "name": model.group[1].name,
                                    },
                                ],
                            },
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                            "groups": {
                                "count": 2,
                                "next": None,
                                "previous": None,
                                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                                "results": [
                                    {
                                        "id": model.group[0].id,
                                        "name": model.group[0].name,
                                    },
                                    {
                                        "id": model.group[1].id,
                                        "name": model.group[1].name,
                                    },
                                ],
                            },
                        },
                    ],
                },
            )


class TestSortBy:
    # countselect
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sort=-id")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )


class TestFilter:
    # countselect
    def test_permission__exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name={model.permission[0].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name!={model.permission[0].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__in(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name={model.permission[0].name},{model.permission[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_in(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name!={model.permission[0].name},{model.permission[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 0,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [],
                },
            )

    # countselect
    def test_permission__iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name~={model.permission[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name!~={model.permission[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__iexact__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?name~={model.permission[0].name.lower()},{model.permission[1].name.lower()}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_iexact__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?name!~={model.permission[0].name.lower()},{model.permission[1].name.lower()}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 0,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [],
                },
            )

    # countselect
    def test_user_model__gt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined>{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[1].id,
                            "username": model.user[1].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__gte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined>={(date_time + timedelta(days=3)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[1].id,
                            "username": model.user[1].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__lt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined<{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[0].id,
                            "username": model.user[0].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__lte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined<={(date_time).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[0].id,
                            "username": model.user[0].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__not_gt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!>{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[0].id,
                            "username": model.user[0].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__not_gte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!>={(date_time + timedelta(days=3)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[0].id,
                            "username": model.user[0].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__not_lt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!<{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[1].id,
                            "username": model.user[1].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__not_lte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!<={(date_time).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[1].id,
                            "username": model.user[1].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__lookup_startswith(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(user=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?username[startswith]={model.user[0].username[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[0].id,
                            "username": model.user[0].username,
                        },
                    ],
                },
            )

    # countselect
    def test_user_model__not_lookup_startswith(
        self, database: capy.Database, django_assert_num_queries, fake: capy.Fake
    ):
        model = database.create(user=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?username![startswith]={model.user[0].username[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.user]),
                {
                    "count": 1,
                    "first": "/user?limit=20&offset=0",
                    "last": "/user?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.user[1].id,
                            "username": model.user[1].username,
                        },
                    ],
                },
            )


class TestFilterM2MQuery:
    # countselect
    def test_permission__exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name={model.group[0].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!={model.group[0].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name~={model.group[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!~={model.group[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__lookup(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name[startswith]={model.group[0].name[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_lookup(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name![startswith]={model.group[0].name[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name={model.group[0].name},{model.group[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!={model.group[0].name},{model.group[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 0,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [],
                },
            )

    # countselect
    def test_permission__iexact__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name~={model.group[0].name.lower()},{model.group[1].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__iexact__not_in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!~={model.group[0].name.lower()},{model.group[1].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 0,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [],
                },
            )


class TestFilterM2OQuery:
    # countselect
    def test_permission__exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, content_type=2)

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?content_type.app_label={model.content_type[0].app_label}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, content_type=2)

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?content_type.app_label!={model.content_type[0].app_label}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=[{"app_label": fake.name().upper()} for _ in range(2)])

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?content_type.app_label~={model.content_type[0].app_label.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=[{"app_label": fake.name().upper()} for _ in range(2)])

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?content_type.app_label!~={model.content_type[0].app_label.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__lookup(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=[{"app_label": fake.name().upper()} for _ in range(2)])

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?content_type.app_label[startswith]={model.content_type[0].app_label[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_lookup(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=2)

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?content_type.app_label![startswith]={model.content_type[0].app_label[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 1,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=2)

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?content_type.app_label={model.content_type[0].app_label},{model.content_type[1].app_label}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__not_in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=2)

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?content_type.app_label!={model.content_type[0].app_label},{model.content_type[1].app_label}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 0,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [],
                },
            )

    # countselect
    def test_permission__iexact__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=[{"app_label": fake.name().upper()} for _ in range(2)])

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?content_type.app_label~={model.content_type[0].app_label.lower()},{model.content_type[1].app_label.lower()}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 2,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": model.permission[0].id,
                            "name": model.permission[0].name,
                        },
                        {
                            "id": model.permission[1].id,
                            "name": model.permission[1].name,
                        },
                    ],
                },
            )

    # countselect
    def test_permission__iexact__not_in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, content_type=[{"app_label": fake.name().upper()} for _ in range(2)])

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?content_type.app_label!~={model.content_type[0].app_label.lower()},{model.content_type[1].app_label.lower()}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[x.id for x in model.permission]),
                {
                    "count": 0,
                    "first": "/permission?limit=20&offset=0",
                    "last": "/permission?limit=20&offset=0",
                    "next": None,
                    "previous": None,
                    "results": [],
                },
            )


class TestHelp:
    def test_permission__filter(self, django_assert_num_queries):
        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?help")

        with django_assert_num_queries(0) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.filter(id__in=[1, 2]),
                {
                    "filters": [
                        "codename",
                        "content_type",
                        "content_type.app_label",
                        "groups",
                        "groups.name",
                        "groups.permissions",
                        "groups.permissions.codename",
                        "groups.permissions.content_type",
                        "groups.permissions.content_type.app_label",
                        "groups.permissions.groups",
                        "groups.permissions.name",
                        "name",
                    ],
                    "sets": [
                        {
                            "fields": [
                                {
                                    "attributes": {
                                        "blank": True,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": False,
                                        "null": False,
                                        "primary_key": True,
                                        "type": "AutoField",
                                    },
                                    "name": "id",
                                },
                                {
                                    "attributes": {
                                        "blank": False,
                                        "choices": 255,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": False,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "CharField",
                                    },
                                    "name": "name",
                                },
                            ],
                            "relationships": [],
                            "set": "default",
                        },
                        {
                            "fields": [
                                {
                                    "attributes": {
                                        "blank": False,
                                        "choices": 100,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": False,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "CharField",
                                    },
                                    "name": "codename",
                                },
                            ],
                            "relationships": [],
                            "set": "extra",
                        },
                        {
                            "fields": [
                                {
                                    "attributes": {
                                        "blank": False,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": True,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "ForeignKey",
                                    },
                                    "name": "content_type",
                                    "type": "pk",
                                },
                            ],
                            "relationships": [],
                            "set": "ids",
                        },
                        {
                            "fields": [],
                            "relationships": [],
                            "set": "lists",
                        },
                        {
                            "fields": [],
                            "relationships": [
                                {
                                    "metadata": {
                                        "blank": False,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": True,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "contenttypes.ContentType",
                                    },
                                    "name": "content_type",
                                    "type": "object",
                                    "sets": [
                                        {
                                            "fields": [
                                                {
                                                    "attributes": {
                                                        "blank": True,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": True,
                                                        "type": "AutoField",
                                                    },
                                                    "name": "id",
                                                },
                                                {
                                                    "attributes": {
                                                        "blank": False,
                                                        "choices": 100,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": False,
                                                        "type": "CharField",
                                                    },
                                                    "name": "app_label",
                                                },
                                            ],
                                            "relationships": [],
                                            "set": "default",
                                        },
                                    ],
                                },
                            ],
                            "set": "expand_ids",
                        },
                        {
                            "fields": [],
                            "relationships": [
                                {
                                    "metadata": {
                                        "blank": True,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": True,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "auth.Group",
                                    },
                                    "name": "groups",
                                    "type": "list",
                                    "sets": [
                                        {
                                            "fields": [
                                                {
                                                    "attributes": {
                                                        "blank": True,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": True,
                                                        "type": "AutoField",
                                                    },
                                                    "name": "id",
                                                },
                                                {
                                                    "attributes": {
                                                        "blank": False,
                                                        "choices": 150,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": False,
                                                        "type": "CharField",
                                                    },
                                                    "name": "name",
                                                },
                                            ],
                                            "relationships": [],
                                            "set": "default",
                                        },
                                        {
                                            "fields": [],
                                            "relationships": [],
                                            "set": "lists",
                                        },
                                        {
                                            "fields": [],
                                            "relationships": [
                                                {
                                                    "metadata": {
                                                        "blank": True,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": True,
                                                        "null": False,
                                                        "primary_key": False,
                                                        "type": "auth.Permission",
                                                    },
                                                    "name": "permissions",
                                                    "sets": [
                                                        {
                                                            "fields": [
                                                                {
                                                                    "attributes": {
                                                                        "blank": True,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": False,
                                                                        "null": False,
                                                                        "primary_key": True,
                                                                        "type": "AutoField",
                                                                    },
                                                                    "name": "id",
                                                                },
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "choices": 255,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": False,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "CharField",
                                                                    },
                                                                    "name": "name",
                                                                },
                                                            ],
                                                            "relationships": [],
                                                            "set": "default",
                                                        },
                                                        {
                                                            "fields": [
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "choices": 100,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": False,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "CharField",
                                                                    },
                                                                    "name": "codename",
                                                                },
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "ForeignKey",
                                                                    },
                                                                    "name": "content_type",
                                                                    "type": "pk",
                                                                },
                                                            ],
                                                            "relationships": [],
                                                            "set": "extra",
                                                        },
                                                        {
                                                            "fields": [
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "ForeignKey",
                                                                    },
                                                                    "name": "content_type",
                                                                    "type": "pk",
                                                                },
                                                            ],
                                                            "relationships": [],
                                                            "set": "ids",
                                                        },
                                                        {
                                                            "fields": [],
                                                            "relationships": [],
                                                            "set": "lists",
                                                        },
                                                        {
                                                            "fields": [],
                                                            "relationships": [
                                                                {
                                                                    "metadata": {
                                                                        "blank": False,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "contenttypes.ContentType",
                                                                    },
                                                                    "name": "content_type",
                                                                    "sets": [
                                                                        {
                                                                            "fields": [
                                                                                {
                                                                                    "attributes": {
                                                                                        "blank": True,
                                                                                        "default": None,
                                                                                        "editable": True,
                                                                                        "help_text": "",
                                                                                        "is_relation": False,
                                                                                        "null": False,
                                                                                        "primary_key": True,
                                                                                        "type": "AutoField",
                                                                                    },
                                                                                    "name": "id",
                                                                                },
                                                                                {
                                                                                    "attributes": {
                                                                                        "blank": False,
                                                                                        "choices": 100,
                                                                                        "default": None,
                                                                                        "editable": True,
                                                                                        "help_text": "",
                                                                                        "is_relation": False,
                                                                                        "null": False,
                                                                                        "primary_key": False,
                                                                                        "type": "CharField",
                                                                                    },
                                                                                    "name": "app_label",
                                                                                },
                                                                            ],
                                                                            "relationships": [],
                                                                            "set": "default",
                                                                        },
                                                                    ],
                                                                    "type": "object",
                                                                },
                                                            ],
                                                            "set": "expand_ids",
                                                        },
                                                        {
                                                            "fields": [],
                                                            "relationships": [
                                                                {
                                                                    "metadata": {
                                                                        "blank": True,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "auth.Group",
                                                                    },
                                                                    "name": "groups",
                                                                    "type": "list",
                                                                },
                                                            ],
                                                            "set": "expand_lists",
                                                        },
                                                    ],
                                                    "type": "list",
                                                },
                                            ],
                                            "set": "expand_lists",
                                        },
                                    ],
                                },
                            ],
                            "set": "expand_lists",
                        },
                    ],
                },
            )

    def test_permission__get(self, django_assert_num_queries):
        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?help")

        with django_assert_num_queries(0) as captured:
            serializer = PermissionSerializer(request=request)

            assert_response(
                serializer.get(id=1),
                {
                    "filters": [
                        "codename",
                        "content_type",
                        "content_type.app_label",
                        "groups",
                        "groups.name",
                        "groups.permissions",
                        "groups.permissions.codename",
                        "groups.permissions.content_type",
                        "groups.permissions.content_type.app_label",
                        "groups.permissions.groups",
                        "groups.permissions.name",
                        "name",
                    ],
                    "sets": [
                        {
                            "fields": [
                                {
                                    "attributes": {
                                        "blank": True,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": False,
                                        "null": False,
                                        "primary_key": True,
                                        "type": "AutoField",
                                    },
                                    "name": "id",
                                },
                                {
                                    "attributes": {
                                        "blank": False,
                                        "choices": 255,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": False,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "CharField",
                                    },
                                    "name": "name",
                                },
                            ],
                            "relationships": [],
                            "set": "default",
                        },
                        {
                            "fields": [
                                {
                                    "attributes": {
                                        "blank": False,
                                        "choices": 100,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": False,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "CharField",
                                    },
                                    "name": "codename",
                                },
                            ],
                            "relationships": [],
                            "set": "extra",
                        },
                        {
                            "fields": [
                                {
                                    "attributes": {
                                        "blank": False,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": True,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "ForeignKey",
                                    },
                                    "name": "content_type",
                                    "type": "pk",
                                },
                            ],
                            "relationships": [],
                            "set": "ids",
                        },
                        {
                            "fields": [],
                            "relationships": [],
                            "set": "lists",
                        },
                        {
                            "fields": [],
                            "relationships": [
                                {
                                    "metadata": {
                                        "blank": False,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": True,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "contenttypes.ContentType",
                                    },
                                    "name": "content_type",
                                    "type": "object",
                                    "sets": [
                                        {
                                            "fields": [
                                                {
                                                    "attributes": {
                                                        "blank": True,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": True,
                                                        "type": "AutoField",
                                                    },
                                                    "name": "id",
                                                },
                                                {
                                                    "attributes": {
                                                        "blank": False,
                                                        "choices": 100,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": False,
                                                        "type": "CharField",
                                                    },
                                                    "name": "app_label",
                                                },
                                            ],
                                            "relationships": [],
                                            "set": "default",
                                        },
                                    ],
                                },
                            ],
                            "set": "expand_ids",
                        },
                        {
                            "fields": [],
                            "relationships": [
                                {
                                    "metadata": {
                                        "blank": True,
                                        "default": None,
                                        "editable": True,
                                        "help_text": "",
                                        "is_relation": True,
                                        "null": False,
                                        "primary_key": False,
                                        "type": "auth.Group",
                                    },
                                    "name": "groups",
                                    "type": "list",
                                    "sets": [
                                        {
                                            "fields": [
                                                {
                                                    "attributes": {
                                                        "blank": True,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": True,
                                                        "type": "AutoField",
                                                    },
                                                    "name": "id",
                                                },
                                                {
                                                    "attributes": {
                                                        "blank": False,
                                                        "choices": 150,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": False,
                                                        "null": False,
                                                        "primary_key": False,
                                                        "type": "CharField",
                                                    },
                                                    "name": "name",
                                                },
                                            ],
                                            "relationships": [],
                                            "set": "default",
                                        },
                                        {
                                            "fields": [],
                                            "relationships": [],
                                            "set": "lists",
                                        },
                                        {
                                            "fields": [],
                                            "relationships": [
                                                {
                                                    "metadata": {
                                                        "blank": True,
                                                        "default": None,
                                                        "editable": True,
                                                        "help_text": "",
                                                        "is_relation": True,
                                                        "null": False,
                                                        "primary_key": False,
                                                        "type": "auth.Permission",
                                                    },
                                                    "name": "permissions",
                                                    "sets": [
                                                        {
                                                            "fields": [
                                                                {
                                                                    "attributes": {
                                                                        "blank": True,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": False,
                                                                        "null": False,
                                                                        "primary_key": True,
                                                                        "type": "AutoField",
                                                                    },
                                                                    "name": "id",
                                                                },
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "choices": 255,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": False,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "CharField",
                                                                    },
                                                                    "name": "name",
                                                                },
                                                            ],
                                                            "relationships": [],
                                                            "set": "default",
                                                        },
                                                        {
                                                            "fields": [
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "choices": 100,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": False,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "CharField",
                                                                    },
                                                                    "name": "codename",
                                                                },
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "ForeignKey",
                                                                    },
                                                                    "name": "content_type",
                                                                    "type": "pk",
                                                                },
                                                            ],
                                                            "relationships": [],
                                                            "set": "extra",
                                                        },
                                                        {
                                                            "fields": [
                                                                {
                                                                    "attributes": {
                                                                        "blank": False,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "ForeignKey",
                                                                    },
                                                                    "name": "content_type",
                                                                    "type": "pk",
                                                                },
                                                            ],
                                                            "relationships": [],
                                                            "set": "ids",
                                                        },
                                                        {
                                                            "fields": [],
                                                            "relationships": [],
                                                            "set": "lists",
                                                        },
                                                        {
                                                            "fields": [],
                                                            "relationships": [
                                                                {
                                                                    "metadata": {
                                                                        "blank": False,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "contenttypes.ContentType",
                                                                    },
                                                                    "name": "content_type",
                                                                    "sets": [
                                                                        {
                                                                            "fields": [
                                                                                {
                                                                                    "attributes": {
                                                                                        "blank": True,
                                                                                        "default": None,
                                                                                        "editable": True,
                                                                                        "help_text": "",
                                                                                        "is_relation": False,
                                                                                        "null": False,
                                                                                        "primary_key": True,
                                                                                        "type": "AutoField",
                                                                                    },
                                                                                    "name": "id",
                                                                                },
                                                                                {
                                                                                    "attributes": {
                                                                                        "blank": False,
                                                                                        "choices": 100,
                                                                                        "default": None,
                                                                                        "editable": True,
                                                                                        "help_text": "",
                                                                                        "is_relation": False,
                                                                                        "null": False,
                                                                                        "primary_key": False,
                                                                                        "type": "CharField",
                                                                                    },
                                                                                    "name": "app_label",
                                                                                },
                                                                            ],
                                                                            "relationships": [],
                                                                            "set": "default",
                                                                        },
                                                                    ],
                                                                    "type": "object",
                                                                },
                                                            ],
                                                            "set": "expand_ids",
                                                        },
                                                        {
                                                            "fields": [],
                                                            "relationships": [
                                                                {
                                                                    "metadata": {
                                                                        "blank": True,
                                                                        "default": None,
                                                                        "editable": True,
                                                                        "help_text": "",
                                                                        "is_relation": True,
                                                                        "null": False,
                                                                        "primary_key": False,
                                                                        "type": "auth.Group",
                                                                    },
                                                                    "name": "groups",
                                                                    "type": "list",
                                                                },
                                                            ],
                                                            "set": "expand_lists",
                                                        },
                                                    ],
                                                    "type": "list",
                                                },
                                            ],
                                            "set": "expand_lists",
                                        },
                                    ],
                                },
                            ],
                            "set": "expand_lists",
                        },
                    ],
                },
            )


class TestGetCacheNoHits:

    # select
    def test_permission__default(self, database: capy.Database, django_assert_num_queries, overwrite_settings):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
        }

        with django_assert_num_queries(1) as captured:
            assert_response(serializer.get(id=model.permission.id), expected)

        key = f"auth.Permission____application/json__en__id={model.permission.id}__"

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # selectm2m select
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries, overwrite_settings):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,ids",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
            "codename": model.permission.codename,
            "content_type": model.permission.content_type.id,
        }

        with django_assert_num_queries(1) as captured:
            assert_response(serializer.get(id=model.permission.id), expected)

        key = f"auth.Permission____application/json__en__id={model.permission.id}__sets=extra,ids"

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # selectm2m select
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries, overwrite_settings):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
            "codename": model.permission.codename,
            "groups": {
                "count": 2,
                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "next": None,
                "previous": None,
                "results": [
                    1,
                    2,
                ],
            },
        }

        with django_assert_num_queries(2) as captured:
            assert_response(serializer.get(id=model.permission.id), expected)

        key = f"auth.Permission____application/json__en__id={model.permission.id}__sets=extra,lists"

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }


class TestFilterCacheNoHits:

    # countselect
    def test_permission__default__two_items(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                },
                {
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                },
            ],
        }

        with django_assert_num_queries(2) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected)

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__"

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # countselect
    def test_permission__two_sets__two_items__ids(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,ids",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "codename": model.permission[0].codename,
                    "content_type": model.permission[0].content_type.id,
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                },
                {
                    "codename": model.permission[1].codename,
                    "content_type": model.permission[1].content_type.id,
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                },
            ],
        }

        with django_assert_num_queries(2) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected)

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__sets=extra,ids"

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # countselectm2m select * 2
    def test_permission__two_sets__two_items__lists(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "codename": model.permission[0].codename,
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "results": [1, 2],
                    },
                },
                {
                    "codename": model.permission[1].codename,
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "results": [1, 2],
                    },
                },
            ],
        }

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__sets=extra,lists"

        with django_assert_num_queries(4) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected)
        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }


class TestGetCacheHits:

    # select
    def test_permission__default(self, database: capy.Database, django_assert_num_queries, overwrite_settings):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
        }

        key = f"auth.Permission____application/json__en__id={model.permission.id}__"
        cache.set(
            key,
            {
                "content": compress(expected),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.get(id=model.permission.id), expected)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # selectm2m select
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries, overwrite_settings):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,ids",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
            "codename": model.permission.codename,
            "content_type": model.permission.content_type.id,
        }

        key = f"auth.Permission____application/json__en__id={model.permission.id}__sets=extra,ids"
        cache.set(
            key,
            {
                "content": compress(expected),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.get(id=model.permission.id), expected)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # selectm2m select
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries, overwrite_settings):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        key = f"auth.Permission____application/json__en__id={model.permission.id}__sets=extra,lists"
        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
            "codename": model.permission.codename,
            "groups": {
                "count": 2,
                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "next": None,
                "previous": None,
                "results": [
                    1,
                    2,
                ],
            },
        }

        cache.set(
            key,
            {
                "content": compress(expected),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.get(id=model.permission.id), expected)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }


class TestFilterCacheHits:

    # countselect
    def test_permission__default__two_items(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                },
                {
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                },
            ],
        }

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__"
        cache.set(
            key,
            {
                "content": compress(expected),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # countselect
    def test_permission__two_sets__two_items__ids(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,ids",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "codename": model.permission[0].codename,
                    "content_type": model.permission[0].content_type.id,
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                },
                {
                    "codename": model.permission[1].codename,
                    "content_type": model.permission[1].content_type.id,
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                },
            ],
        }

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__sets=extra,ids"
        cache.set(
            key,
            {
                "content": compress(expected),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }

    # countselectm2m select * 2
    def test_permission__two_sets__two_items__lists(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 10)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "codename": model.permission[0].codename,
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "results": [1, 2],
                    },
                },
                {
                    "codename": model.permission[1].codename,
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "results": [1, 2],
                    },
                },
            ],
        }

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__sets=extra,lists"
        cache.set(
            key,
            {
                "content": compress(expected),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key)) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
            },
        }


class TestFilterCompressingCacheNoHits:

    # countselectm2m select * 2
    @pytest.mark.parametrize("encoding", ["gzip", "br", "deflate", "zstd"])
    def test_permission__two_sets__two_items__lists(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings, encoding
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 0)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
                "Accept-Encoding": encoding,
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "codename": model.permission[0].codename,
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "results": [1, 2],
                    },
                },
                {
                    "codename": model.permission[1].codename,
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "results": [1, 2],
                    },
                },
            ],
        }

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__sets=extra,lists"

        with django_assert_num_queries(4) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected, encoding=encoding)
        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key), encoding=encoding) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
                "Content-Encoding": encoding,
            },
        }


class TestFilterCompressingCacheHits:

    # countselectm2m select * 2
    @pytest.mark.parametrize("encoding", ["gzip", "br", "deflate", "zstd"])
    def test_permission__two_sets__two_items__lists(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings, encoding
    ):
        model = database.create(permission=2, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 0)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
                "Accept-Encoding": encoding,
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []
        expected = {
            "count": 2,
            "first": "/permission?limit=20&offset=0",
            "last": "/permission?limit=20&offset=0",
            "next": None,
            "previous": None,
            "results": [
                {
                    "codename": model.permission[0].codename,
                    "id": model.permission[0].id,
                    "name": model.permission[0].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[0].id}",
                        "results": [1, 2],
                    },
                },
                {
                    "codename": model.permission[1].codename,
                    "id": model.permission[1].id,
                    "name": model.permission[1].name,
                    "groups": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "first": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "last": f"/group?limit=20&offset=0&permissions.pk={model.permission[1].id}",
                        "results": [1, 2],
                    },
                },
            ],
        }

        key = f"auth.Permission____application/json__en__id__in=[{', '.join([str(x.id) for x in model.permission])}]__sets=extra,lists"
        cache.set(
            key,
            {
                "content": compress(expected, encoding=encoding),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                    "Content-Encoding": encoding,
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.filter(id__in=[x.id for x in model.permission]), expected, encoding=encoding)
        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key), encoding=encoding) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
                "Content-Encoding": encoding,
            },
        }


class TestGetCompressingCacheNoHits:

    # selectm2m select
    @pytest.mark.parametrize("encoding", ["gzip", "br", "deflate", "zstd"])
    def test_permission__two_sets__lists(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings, encoding
    ):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 0)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
                "Accept-Encoding": encoding,
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        key = f"auth.Permission____application/json__en__id={model.permission.id}__sets=extra,lists"
        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
            "codename": model.permission.codename,
            "groups": {
                "count": 2,
                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "next": None,
                "previous": None,
                "results": [
                    1,
                    2,
                ],
            },
        }

        with django_assert_num_queries(2) as captured:
            assert_response(serializer.get(id=model.permission.id), expected, encoding=encoding)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key), encoding=encoding) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
                "Content-Encoding": encoding,
            },
        }


class TestGetCompressingCacheHits:

    # selectm2m select
    @pytest.mark.parametrize("encoding", ["gzip", "br", "deflate", "zstd"])
    def test_permission__two_sets__lists(
        self, database: capy.Database, django_assert_num_queries, overwrite_settings, encoding
    ):
        model = database.create(permission=1, group=2)
        overwrite_settings("is_cache_enabled", True)
        overwrite_settings("min_compression_size", 0)

        factory = APIRequestFactory()
        request = factory.get(
            "/notes/547/?sets=extra,lists",
            headers={
                "Accept": "application/json",
                "Accept-Language": "en",
                "Accept-Encoding": encoding,
            },
        )

        serializer = PermissionSerializer(request=request)
        assert cache.keys("*") == []

        key = f"auth.Permission____application/json__en__id={model.permission.id}__sets=extra,lists"
        expected = {
            "id": model.permission.id,
            "name": model.permission.name,
            "codename": model.permission.codename,
            "groups": {
                "count": 2,
                "first": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "last": f"/group?limit=20&offset=0&permissions.pk={model.permission.id}",
                "next": None,
                "previous": None,
                "results": [
                    1,
                    2,
                ],
            },
        }

        cache.set(
            key,
            {
                "content": compress(expected, encoding=encoding),
                "headers": {
                    "Cache-Control": "public",
                    "Content-Type": "application/json",
                    "Content-Encoding": encoding,
                },
            },
        )

        with django_assert_num_queries(0) as captured:
            assert_response(serializer.get(id=model.permission.id), expected, encoding=encoding)

        assert cache.keys("*") == [
            key,
        ]

        assert decompress(cache.get(key), encoding=encoding) == {
            "content": expected,
            "headers": {
                "Cache-Control": "public",
                "Content-Type": "application/json",
                "Content-Encoding": encoding,
            },
        }
