# Field sets

Capy Serializers supports field sets, you can set `sets` attribute in the serializer, by default the fields provided in `default` set always are included in the response.

In contract with `OData`, the `sets` parameter determines the included and expanded fields in the response.

## Request

```http
GET /api/v1/users?sets=default,custom
```

## Serializer

```python
import capyc.django.serializer as capy

class PermissionSerializer(capy.Serializer):
    fields = {
        "default": ("id", "name"),
        "extra": ("codename", "content_type"),
        "ids": ("content_type", "groups"),
        "lists": ("groups",),
        "expand_ids": ("content_type[]",),
        "expand_lists": ("groups[]",),
    }
```
