# Cache

Capy Serializers supports caching out of the box, with caching enabled by default. This package utilizes [django-redis](https://github.com/jazzband/django-redis).

## Settings

```python
CAPYC = {
    "cache": {
        "enabled": True,
    }
}
```
