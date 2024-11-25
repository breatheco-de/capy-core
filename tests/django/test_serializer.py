from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection, models
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory

import capyc.pytest as capy
from capyc.django.serializer import Serializer


@pytest.fixture(autouse=True)
def setup(db):
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


@pytest.fixture(autouse=True)
def setup(db):
    yield


class TestNoExpandGet:

    # select
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(1) as captured:
            assert serializer.get(id=model.permission.id) == {
                "id": model.permission.id,
                "name": model.permission.name,
            }

    # selectm2m select
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,ids")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(1) as captured:
            assert serializer.get(id=model.permission.id) == {
                "id": model.permission.id,
                "name": model.permission.name,
                "codename": model.permission.codename,
                "content_type": model.permission.content_type.id,
            }

    # selectm2m select
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,lists")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(2) as captured:
            assert serializer.get(id=model.permission.id) == {
                "id": model.permission.id,
                "name": model.permission.name,
                "codename": model.permission.codename,
                "groups": {
                    "count": 2,
                    "first": f"/group?limit=20&offset=0&permissions={model.permission.id}",
                    "last": f"/group?limit=20&offset=0&permissions={model.permission.id}",
                    "next": None,
                    "previous": None,
                    "results": [
                        1,
                        2,
                    ],
                },
            }


class TestNoExpandFilter:

    # countselect
    def test_permission__default__two_items(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(2) as captured:
            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

    # countselect
    def test_permission__two_sets__two_items__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,ids")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(2) as captured:
            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

    # countselectm2m select * 2
    def test_permission__two_sets__two_items__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=extra,lists")

        serializer = PermissionSerializer(request=request)

        with django_assert_num_queries(4) as captured:
            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
                            "first": f"/group?limit=20&offset=0&permissions={model.permission[0].id}",
                            "last": f"/group?limit=20&offset=0&permissions={model.permission[0].id}",
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
                            "first": f"/group?limit=20&offset=0&permissions={model.permission[1].id}",
                            "last": f"/group?limit=20&offset=0&permissions={model.permission[1].id}",
                            "results": [1, 2],
                        },
                    },
                ],
            }


class TestExpandGet:
    # selectm2m select
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        with django_assert_num_queries(1) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.get(id=model.permission.id) == {
                "id": model.permission.id,
                "name": model.permission.name,
            }

    # select
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_ids")

        with django_assert_num_queries(1) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.get(id=model.permission.id) == {
                "id": model.permission.id,
                "name": model.permission.name,
                "content_type": {
                    "id": model.permission.content_type.id,
                    "app_label": model.permission.content_type.app_label,
                },
            }

    # selectm2m select
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=1, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_lists")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.get(id=model.permission.id) == {
                "id": model.permission.id,
                "name": model.permission.name,
                "groups": {
                    "count": 2,
                    "next": None,
                    "previous": None,
                    "first": f"/group?limit=20&offset=0&permissions={model.permission.id}",
                    "last": f"/group?limit=20&offset=0&permissions={model.permission.id}",
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
            }


class TestExpandFilter:
    # countselect
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

    # countselect
    def test_permission__two_sets__ids(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_ids")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselectm2m select * 2
    def test_permission__two_sets__lists(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sets=intro,expand_lists")

        with django_assert_num_queries(4) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
                            "first": f"/group?limit=20&offset=0&permissions={model.permission[0].id}",
                            "last": f"/group?limit=20&offset=0&permissions={model.permission[0].id}",
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
                            "first": f"/group?limit=20&offset=0&permissions={model.permission[1].id}",
                            "last": f"/group?limit=20&offset=0&permissions={model.permission[1].id}",
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
            }


class TestSortBy:
    # countselect
    def test_permission__default(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get("/notes/547/?sort=-id")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }


# class TestGet:
#     # countselect
#     def test_permission__exact(self, database: capy.Database, django_assert_num_queries):
#         model = database.create(permission=2, group=2)

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?name={model.permission[0].name}")

#         with django_assert_num_queries(2) as captured:
#             serializer = PermissionSerializer(request=request)

#             assert serializer.get(id=model.permission.id) == {
#                 "count": 1,
#                 "first": "/permission?limit=20&offset=0",
#                 "last": "/permission?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.permission[0].id,
#                         "name": model.permission[0].name,
#                     },
#                 ],
#             }

#     # countselect
#     def test_permission__not_exact(self, database: capy.Database, django_assert_num_queries):
#         model = database.create(permission=2, group=2)

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?name!={model.permission[0].name}")

#         with django_assert_num_queries(2) as captured:
#             serializer = PermissionSerializer(request=request)

#             assert serializer.get(id=model.permission.id) == {
#                 "count": 1,
#                 "first": "/permission?limit=20&offset=0",
#                 "last": "/permission?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.permission[1].id,
#                         "name": model.permission[1].name,
#                     },
#                 ],
#             }


#     # countselect
#     def test_permission__iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?name~={model.permission[0].name.lower()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = PermissionSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.permission]) == {
#                 "count": 1,
#                 "first": "/permission?limit=20&offset=0",
#                 "last": "/permission?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.permission[0].id,
#                         "name": model.permission[0].name,
#                     },
#                 ],
#             }

#     # countselect
#     def test_permission__not_iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?name!~={model.permission[0].name.lower()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = PermissionSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.permission]) == {
#                 "count": 1,
#                 "first": "/permission?limit=20&offset=0",
#                 "last": "/permission?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.permission[1].id,
#                         "name": model.permission[1].name,
#                     },
#                 ],
#             }


#     # countselect
#     def test_user_model__gt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined>{(date_time + timedelta(days=1)).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[1].id,
#                         "username": model.user[1].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__gte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined>={(date_time + timedelta(days=3)).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[1].id,
#                         "username": model.user[1].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__lt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined<{(date_time + timedelta(days=1)).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[0].id,
#                         "username": model.user[0].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__lte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined<={(date_time).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[0].id,
#                         "username": model.user[0].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__not_gt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined!>{(date_time + timedelta(days=1)).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[0].id,
#                         "username": model.user[0].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__not_gte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined!>={(date_time + timedelta(days=3)).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[0].id,
#                         "username": model.user[0].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__not_lt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined!<{(date_time + timedelta(days=1)).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[1].id,
#                         "username": model.user[1].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__not_lte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         date_time = fake.date_time()
#         model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?date_joined!<={(date_time).isoformat()}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[1].id,
#                         "username": model.user[1].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__lookup_startswith(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
#         model = database.create(user=2)

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?username[startswith]={model.user[0].username[:3]}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[0].id,
#                         "username": model.user[0].username,
#                     },
#                 ],
#             }

#     # countselect
#     def test_user_model__not_lookup_startswith(
#         self, database: capy.Database, django_assert_num_queries, fake: capy.Fake
#     ):
#         model = database.create(user=2)

#         factory = APIRequestFactory()
#         request = factory.get(f"/notes/547/?username![startswith]={model.user[0].username[:3]}")

#         with django_assert_num_queries(2) as captured:
#             serializer = UserSerializer(request=request)

#             assert serializer.filter(id__in=[x.id for x in model.user]) == {
#                 "count": 1,
#                 "first": "/user?limit=20&offset=0",
#                 "last": "/user?limit=20&offset=0",
#                 "next": None,
#                 "previous": None,
#                 "results": [
#                     {
#                         "id": model.user[1].id,
#                         "username": model.user[1].username,
#                     },
#                 ],
#             }


class TestFilter:
    # countselect
    def test_permission__exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name={model.permission[0].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__not_exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name!={model.permission[0].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__in(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name={model.permission[0].name},{model.permission[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

    # countselect
    def test_permission__not_in(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name!={model.permission[0].name},{model.permission[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
                "count": 0,
                "first": "/permission?limit=20&offset=0",
                "last": "/permission?limit=20&offset=0",
                "next": None,
                "previous": None,
                "results": [],
            }

    # countselect
    def test_permission__iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name~={model.permission[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__not_iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?name!~={model.permission[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__iexact__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?name~={model.permission[0].name.lower()},{model.permission[1].name.lower()}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

    # countselect
    def test_permission__not_iexact__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=[{"name": fake.name().upper()} for _ in range(2)], group=2)

        factory = APIRequestFactory()
        request = factory.get(
            f"/notes/547/?name!~={model.permission[0].name.lower()},{model.permission[1].name.lower()}"
        )

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
                "count": 0,
                "first": "/permission?limit=20&offset=0",
                "last": "/permission?limit=20&offset=0",
                "next": None,
                "previous": None,
                "results": [],
            }

    # countselect
    def test_user_model__gt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined>{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__gte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined>={(date_time + timedelta(days=3)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__lt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined<{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__lte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined<={(date_time).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__not_gt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!>{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__not_gte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!>={(date_time + timedelta(days=3)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__not_lt(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!<{(date_time + timedelta(days=1)).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__not_lte(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        date_time = fake.date_time()
        model = database.create(user=[{"date_joined": date_time}, {"date_joined": date_time + timedelta(days=3)}])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?date_joined!<={(date_time).isoformat()}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__lookup_startswith(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(user=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?username[startswith]={model.user[0].username[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }

    # countselect
    def test_user_model__not_lookup_startswith(
        self, database: capy.Database, django_assert_num_queries, fake: capy.Fake
    ):
        model = database.create(user=2)

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?username![startswith]={model.user[0].username[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = UserSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.user]) == {
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
            }


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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__not_exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!={model.group[0].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name~={model.group[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__not_iexact(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!~={model.group[0].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__lookup(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name[startswith]={model.group[0].name[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__not_lookup(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name![startswith]={model.group[0].name[:3]}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

    # countselect
    def test_permission__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name={model.group[0].name},{model.group[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

    # countselect
    def test_permission__not_in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=2)
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!={model.group[0].name},{model.group[1].name}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
                "count": 0,
                "first": "/permission?limit=20&offset=0",
                "last": "/permission?limit=20&offset=0",
                "next": None,
                "previous": None,
                "results": [],
            }

    # countselect
    def test_permission__iexact__in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name~={model.group[0].name.lower()},{model.group[1].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

    # countselect
    def test_permission__iexact__not_in(self, database: capy.Database, django_assert_num_queries, fake: capy.Fake):
        model = database.create(permission=2, group=[{"name": fake.name().upper()} for _ in range(2)])
        model.group[0].permissions.set([model.permission[0]])
        model.group[1].permissions.set([model.permission[1]])

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?groups.name!~={model.group[0].name.lower()},{model.group[1].name.lower()}")

        with django_assert_num_queries(2) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
                "count": 0,
                "first": "/permission?limit=20&offset=0",
                "last": "/permission?limit=20&offset=0",
                "next": None,
                "previous": None,
                "results": [],
            }


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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }

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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
                "count": 0,
                "first": "/permission?limit=20&offset=0",
                "last": "/permission?limit=20&offset=0",
                "next": None,
                "previous": None,
                "results": [],
            }

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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
                "count": 0,
                "first": "/permission?limit=20&offset=0",
                "last": "/permission?limit=20&offset=0",
                "next": None,
                "previous": None,
                "results": [],
            }


class TestHelp:
    # countselect
    def test_permission__exact(self, database: capy.Database, django_assert_num_queries):
        model = database.create(permission=2, content_type=2)

        model.permission[0].content_type = model.content_type[0]
        model.permission[0].save()

        model.permission[1].content_type = model.content_type[1]
        model.permission[1].save()

        factory = APIRequestFactory()
        request = factory.get(f"/notes/547/?help")

        with django_assert_num_queries(0) as captured:
            serializer = PermissionSerializer(request=request)

            assert serializer.filter(id__in=[x.id for x in model.permission]) == {
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
            }
