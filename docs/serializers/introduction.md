# Capy Serializers

Capy Serializers is a propose to replace DRF's Serializer, Serpy, and API View Extensions, the main difference respect to them is that Capy Serializers returns a Django Rest Framework compatible response.

## Usage

```python
import capyc.django.serializer as capy

class PermissionSerializer(capy.Serializer):
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

```

## Features

- [Field sets](field-sets.md).
- [Fields and filters overrides](fields-overrides.md).
- [Query params](query-params.md).
- [Pagination](pagination.md).
- [Sort by](sort-by.md).
- [Help](help.md).
- [Compression](compression.md).
- [Cache](cache.md).
- [Cache ttl](cache-ttl.md).
- [Cache control](cache-control.md).
- [Query optimizations](query-optimizations.md).
- [Query depth](query-depth.md).
