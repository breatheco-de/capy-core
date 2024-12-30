import asyncio
import os

from adrf.decorators import api_view
from django.http import HttpRequest
from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from capyc.django.cache import delete_cache
from capyc.rest_framework.exceptions import ValidationException

# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# async def revalidate_cache(request: HttpRequest):
#     capy_key = os.getenv("CAPY_KEY")
#     if not capy_key:
#         raise ValidationException("CAPY_KEY not configured")

#     key = request.data.get("key")
#     if not key:
#         raise ValidationException("Key is required")

#     if not isinstance(key, str):
#         raise ValidationException("Key must be a string")

#     if key != os.getenv("CAPY_KEY"):
#         raise ValidationException("Invalid key")

#     serializer = request.data.get("serializer")
#     if not serializer:
#         raise ValidationException("Serializer is required")

#     if not isinstance(serializer, str):
#         raise ValidationException("Serializer must be a string")

#     await delete_cache(serializer)

#     return Response(None, status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
async def delete_cache(request: HttpRequest):
    capy_key = os.getenv("CAPY_KEY")
    if not capy_key:
        raise ValidationException("CAPY_KEY not configured")

    key = request.data.get("key")
    if not key:
        raise ValidationException("Key is required")

    if not isinstance(key, str):
        raise ValidationException("Key must be a string")

    if key != os.getenv("CAPY_KEY"):
        raise ValidationException("Invalid key")

    serializer = request.data.get("serializer")
    if not serializer:
        raise ValidationException("Serializer is required")

    if not isinstance(serializer, str):
        raise ValidationException("Serializer must be a string")

    await delete_cache(serializer)

    return Response(None, status=status.HTTP_204_NO_CONTENT)
