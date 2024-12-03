# Compression

Capy Serializers supports compression out of the box, with compression enabled by default. This package supports `gzip`, `deflate`, `brotli`, and `zstandard`.

## Settings

```python
CAPYC = {
    "compression": {
        "enabled": True,
        "min_kb_size": 10,
    }
}
```
