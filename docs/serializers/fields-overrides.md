# Fields and filters overrides.

Capy Serializers supports overwrites fields names.

## Example

```python
import capyc.django.serializer as capy

class PermissionSerializer(capy.Serializer):
    model = Permission
    fields = {
        "default": ("id", "name"),
        "lists": ("groups",),
        "expand_lists": ("groups[]",),
    }
    rewrites = {
        "group_set": "groups",
    }
    filters = ("groups",)
    groups = GroupSerializer
```
