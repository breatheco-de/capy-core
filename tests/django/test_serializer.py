import pytest
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIRequestFactory

import capyc.pytest as capy
from capyc.django.serializer import Serializer


class ContentTypeSerializer(Serializer):
    model = ContentType
    fields = {
        "default": ("id", "app_label"),
    }
    filters = ("app_label", "content_type")
    depth = 2


class PermissionSerializer(Serializer):
    model = Permission
    fields = {
        "default": ("id", "name"),
        "contact": ("codename", "content_type"),
        "ids": ("content_type",),
    }
    filters = ("name", "codename")
    depth = 2
    content_type = ContentTypeSerializer()


class GroupSerializer(Serializer):
    model = Group
    fields = {
        "default": ("id", "name"),
        "lists": ("permissions",),
    }
    filters = "name"
    depth = 2

    permissions = PermissionSerializer(many=True)


class UserSerializer(Serializer):
    model = User
    fields = {
        "default": ("id", "username"),
        "intro": ("first_name", "last_name"),
        "lists": ("groups", "permissions"),
    }
    filters = ("slug", "name", "academy__*")
    depth = 2

    groups = GroupSerializer(many=True)
    permissions = PermissionSerializer(many=True)


# class UserSerializer(Serializer):
#     # model = Cohort
#     fields = {
#         "default": ("id", "name", "slug"),
#         "intro": ("intro_video", "available_as_saas"),
#         "ids": ("academy", "syllabus_version"),
#     }
#     filters = ("slug", "name", "academy__*")
#     depth = 2

#     academy = AcademySerializer()
#     # academy = AcademySerializer(sets=["available_as_saas"])


@pytest.fixture(autouse=True)
def setup(db):
    yield


@pytest.mark.django_db(reset_sequences=True)
def test_default(database: capy.Database):
    model = database.create(permission=2)

    qs = Permission.objects.filter(id__in=[x.id for x in model.permission]).order_by("id")
    serializer = PermissionSerializer(data=qs, many=True)

    assert serializer.data == [
        {
            "id": x.id,
            "name": x.name,
        }
        for x in model.permission
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_some_sets(database: capy.Database):
    model = await database.acreate(permission=2)

    factory = APIRequestFactory()
    request = factory.get("/notes/547/?sets=intro,not-found")

    qs = Permission.objects.filter(id__in=[x.id for x in model.permission]).order_by("id")
    serializer = PermissionSerializer(data=qs, many=True, request=request)

    assert await serializer.adata == [
        {
            "id": x.id,
            "name": x.name,
        }
        for x in model.permission
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_one_set(database: capy.Database):
    model = await database.acreate(permission=2)

    factory = APIRequestFactory()
    request = factory.get("/notes/547/?sets=intro,not-found")

    qs = Permission.objects.filter(id__in=[x.id for x in model.permission]).order_by("id")
    serializer = PermissionSerializer(data=qs, many=True, request=request)

    assert await serializer.adata == [
        {
            "id": x.id,
            "name": x.name,
        }
        for x in model.permission
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_two_sets(database: capy.Database):
    model = await database.acreate(permission=2)

    factory = APIRequestFactory()
    request = factory.get("/notes/547/?sets=intro,ids")

    qs = Permission.objects.filter(id__in=[x.id for x in model.permission]).order_by("id")
    serializer = PermissionSerializer(data=qs, many=True, request=request)

    assert await serializer.adata == [
        {
            "id": x.id,
            "name": x.name,
            "content_type": x.content_type.id,
        }
        for x in model.permission
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_two_sets_expanded(database: capy.Database):
    model = await database.acreate(permission=2)

    factory = APIRequestFactory()
    request = factory.get("/notes/547/?sets=intro,ids&expand=content_type")

    qs = Permission.objects.filter(id__in=[x.id for x in model.permission]).order_by("id")
    serializer = PermissionSerializer(data=qs, many=True, request=request)

    assert await serializer.adata == [
        {
            "id": x.id,
            "name": x.name,
            "content_type": {
                "id": x.content_type.id,
                "app_label": x.content_type.app_label,
            },
        }
        for x in model.permission
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_two_sets_expanded___(database: capy.Database):
    model = await database.acreate(permission=2)

    factory = APIRequestFactory()
    request = factory.get("/notes/547/?sets=intro,ids,academy[contact,saas]&expand=content_type")

    qs = Permission.objects.filter(id__in=[x.id for x in model.permission]).order_by("id")
    serializer = PermissionSerializer(data=qs, many=True, request=request)

    assert await serializer.adata == [
        {
            "id": x.id,
            "name": x.name,
            "content_type": {
                "id": x.content_type.id,
                "app_label": x.content_type.app_label,
            },
        }
        for x in model.permission
    ]


# @pytest.mark.asyncio
# @pytest.mark.django_db(reset_sequences=True)
# async def test_two_sets_expanded___(database: capy.Database):
#     model = await database.acreate(cohort=2)

#     factory = APIRequestFactory()
#     request = factory.get("/notes/547/?sets=intro,ids&expand=academy[contact,saas],syllabus_version")

#     qs = Permission.objects.filter(id__in=[x.id for x in model.permission]).order_by("id")
#     serializer = PermissionSerializer(data=qs, many=True, request=request)

#     assert await serializer.adata == [
#         {
#             "id": x.id,
#             "slug": x.slug,
#             "name": x.name,
#             "intro_video": x.intro_video,
#             "available_as_saas": x.available_as_saas,
#             "academy": {
#                 "id": x.academy.id,
#                 "name": x.academy.name,
#                 "slug": x.academy.slug,
#                 "street_address": x.academy.street_address,
#                 "feedback_email": x.academy.feedback_email,
#                 "available_as_saas": x.academy.available_as_saas,
#                 "is_hidden_on_prework": x.academy.is_hidden_on_prework,
#             },
#             "syllabus_version": None,
#         }
#         for x in model.cohort
#     ]
