# Cache control

Capy Serializers supports cache control. You can set the `cache_control` attribute in the serializer to define the [cache control](https://developer.mozilla.org/es/docs/Web/HTTP/Headers/Cache-Control) headers, which can include directives such as `no-cache`, `no-store`, `must-revalidate`, `max-age`, and `public` or `private` to control how responses are cached by browsers and intermediate caches.

## Example

```python
import capyc.django.serializer as capy

class PermissionSerializer(capy.Serializer):
    cache_control = f"max-age={60 * 60}"  # 1 hour
```
