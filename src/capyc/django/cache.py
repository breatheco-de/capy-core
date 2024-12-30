import asyncio
import gzip
import importlib
import json
import os
import sys
import zlib
from functools import lru_cache
from typing import Any, Type, TypedDict

import brotli
import zstandard
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q
from django.http import HttpResponse
from rest_framework import status

try:
    import celery  # noqa: F401

    CELERY_INSTALLED = True

except ImportError:
    CELERY_INSTALLED = False


# not supported yet
# from django.db.models import OuterRef, Subquery, Min, Max, Avg, Sum, Count, StdDev, Variance

# annotate json fields
# from django.db.models.fields.json import KT


__all__ = ["set_cache", "get_cache", "delete_cache", "reset_cache", "settings", "Filter", "Annotate", "Aggregate"]

IS_DJANGO_REDIS = hasattr(cache, "delete_pattern")
FALSE_VALUES = ["false", "0", "no", "off", "False", "FALSE", "false", "N", "No", "NO", "Off", "OFF"]

CAPYC = getattr(settings, "CAPYC", {})
if "cache" in CAPYC and isinstance(CAPYC["cache"], dict):
    is_cache_enabled = bool(CAPYC["cache"].get("enabled", True))

else:
    is_cache_enabled = os.getenv("CAPYC_CACHE", "True") not in FALSE_VALUES

if "compression" in CAPYC and isinstance(CAPYC["compression"], dict):
    is_compression_enabled = bool(CAPYC["compression"].get("enabled", True))
    min_compression_size = int(CAPYC["compression"].get("min_kb_size", 10))

else:
    is_compression_enabled = os.getenv("CAPYC_COMPRESSION", "True") not in FALSE_VALUES
    min_compression_size = int(os.getenv("CAPYC_MIN_COMPRESSION_SIZE", "10"))


class Settings(TypedDict):
    min_compression_size: int
    is_cache_enabled: bool
    is_compression_enabled: bool


settings: Settings = {
    "min_compression_size": min_compression_size,
    "is_cache_enabled": is_cache_enabled,
    "is_compression_enabled": is_compression_enabled,  # not used yet
}

type Params = tuple[tuple[Q | F, ...], dict[str, Any]]


def key_builder(serializer: str, params: Params, query: list[str], headers: dict[str, str]):
    accept = headers.get("Accept", "application/json")
    encoding = headers.get("Content-Encoding", "")
    acceptLanguage = headers.get("Accept-Language", "")

    if "zstd" in encoding:
        encoding = "zstd"
    elif "br" in encoding:
        encoding = "br"
    elif "gzip" in encoding:
        encoding = "gzip"
    elif "deflate" in encoding:
        encoding = "deflate"
    else:
        encoding = ""

    args = params[0]
    kwargs = params[1]

    return "__".join(
        [
            serializer,
            encoding,
            accept,
            acceptLanguage,
            "&".join([str(arg) for arg in args]),
            "&".join([f"{x}={y}" for x, y in sorted(kwargs.items())]),
            "&".join(sorted(query)),
        ]
    )


def compress(value: Any, headers: dict[str, str], cache_control: str | None = None):
    encoding = headers.get("Accept-Encoding", "")
    # until support other content types
    contentType = "application/json"

    response = {
        "headers": {},
        "content": None,
    }

    value = json.dumps(value).encode("utf-8")

    if (
        sys.getsizeof(value) / 1024 <= settings["min_compression_size"]
        or (cache_control and "no-store" in cache_control)
        or ("no-store" in headers.get("Cache-Control", ""))
    ):
        response["content"] = value
        response["headers"]["Content-Type"] = contentType
        return response

    # faster option, it should be the standard in the future
    if "zstd" in encoding:
        response["content"] = zstandard.compress(value)
        response["headers"]["Content-Encoding"] = "zstd"
        response["headers"]["Content-Type"] = contentType

    elif "br" in encoding:
        response["content"] = brotli.compress(value)
        response["headers"]["Content-Encoding"] = "br"
        response["headers"]["Content-Type"] = contentType

    elif "gzip" in encoding:
        response["content"] = gzip.compress(value)
        response["headers"]["Content-Encoding"] = "gzip"
        response["headers"]["Content-Type"] = contentType

    elif "deflate" in encoding:
        response["content"] = zlib.compress(value)
        response["headers"]["Content-Encoding"] = "deflate"
        response["headers"]["Content-Type"] = contentType

    else:
        response["content"] = value
        response["headers"]["Content-Type"] = contentType

    return response


def get_cache(serializer: str, params: Params, query: list[str], headers: dict[str, str]):
    if settings["is_cache_enabled"] is False or headers.get("Cache-Control", "") in ["no-store", "no-cache"]:
        return None

    key = key_builder(serializer, params, query, headers)

    res = cache.get(key)
    if res is None:
        return None

    # implement other content types
    return HttpResponse(res["content"], status=status.HTTP_200_OK, headers=res["headers"])


def set_cache(
    serializer: str,
    value: Any,
    ttl: int | None,
    params: Params,
    query: list[str],
    headers: dict[str, str],
    cache_control: str | None = None,
):
    if settings["is_cache_enabled"] is False:
        # implement other content types
        return HttpResponse(json.dumps(value), status=status.HTTP_200_OK, headers={"Content-Type": "application/json"})

    key = key_builder(serializer, params, query, headers)

    res = compress(value, headers)

    if "Authorization" in headers:
        res["headers"]["Cache-Control"] = "private"

    elif cache_control:
        res["headers"]["Cache-Control"] = cache_control

    # elif ttl:
    #     res["headers"]["Cache-Control"] = f"max-age={ttl}"
    #     res["headers"]["Expires"] = (timezone.now() + timedelta(seconds=ttl)).isoformat()

    else:
        res["headers"]["Cache-Control"] = "public"

    if res["headers"]["Cache-Control"] != "no-store":
        cache.set(key, res, ttl)

    # implement other content types
    return HttpResponse(res["content"], status=status.HTTP_200_OK, headers=res["headers"])


@lru_cache(maxsize=1000)
def has_static_handler(key: str) -> bool:
    from .serializer import Serializer

    parts = key.split(".")
    module_name = ".".join(parts[:-1])
    serializer_name = ".".join(parts[-1:])

    module = importlib.import_module(module_name)

    serializer_cls: Type[Serializer] = getattr(module, serializer_name)
    return serializer_cls.revalidate is not None


async def delete_cache(key: str):
    from .serializer import SERIALIZER_DEPTHS, SERIALIZER_PARENTS, SERIALIZER_REGISTRY

    async def clean_node(key: str, depth: int = 0):
        depth += 1

        if depth <= SERIALIZER_DEPTHS.get(key, 0):
            cache.delete_pattern(f"{key}*")
            if CELERY_INSTALLED:
                from .tasks import revalidate_cache

                if has_static_handler(key):
                    revalidate_cache.delay(key)

        promises = []

        for serializer in SERIALIZER_PARENTS.get(key, set()):
            promises.append(clean_node(serializer, depth))

        await asyncio.gather(*promises)

    if key in SERIALIZER_REGISTRY:
        promises = []
        for serializer in SERIALIZER_REGISTRY[key]:
            promises.append(clean_node(serializer))

        await asyncio.gather(*promises)

    await clean_node(key)


async def reset_cache():
    cache.delete_pattern("*")
