# Query depth

Capy Serializers supports query depth, you can set `depth` attribute in the serializer to limit the depth of the query. Default depth is 2.

## Example

```python
import capyc.django.serializer as capy

class PermissionSerializer(capy.Serializer):
    depth = 3
```
