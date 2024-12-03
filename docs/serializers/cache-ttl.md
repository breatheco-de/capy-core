# Cache ttl

Capy Serializers supports set a custom time to live for the cache, you can set `ttl` attribute in the serializer to set the cache ttl, after this time the cache will be invalidated. This value is in seconds.

## Example

```python
import capyc.django.serializer as capy

class PermissionSerializer(capy.Serializer):
    ttl = 60 * 60  # 1 hour
```
