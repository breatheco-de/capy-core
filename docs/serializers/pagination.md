# Pagination

Capy Serializers supports pagination out of the box, this feature cannot be disabled, you must provide the attribute `path` to the serializer to enable the links. This package supports `limit` and `offset` query params. Like GraphQL, all nested queries are automatically paginated. If you want to load more results, you can use the `next` link in the response.

## Example

```json
{
    "count": 100,
    "previous": "http://localhost:8000/api/v1/users/?limit=10&offset=0",
    "next": "http://localhost:8000/api/v1/users/?limit=10&offset=10",
    "first": "http://localhost:8000/api/v1/users/?limit=10&offset=0",
    "last": "http://localhost:8000/api/v1/users/?limit=10&offset=90",
    "results": [
        ...
        "nested_m2m": {
            "count": 100,
            "previous": "http://localhost:8000/api/v1/m2m/?limit=10&offset=0",
            "next": "http://localhost:8000/api/v1/m2m/?limit=10&offset=10",
            "first": "http://localhost:8000/api/v1/m2m/?limit=10&offset=0",
            "last": "http://localhost:8000/api/v1/m2m/?limit=10&offset=90",
            "results": [
                ...
            ]
        }
    ]
}
```
