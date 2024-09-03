# aclient

Async wrapper of [APIClient](https://www.django-rest-framework.org/api-guide/testing/#apiclient).

## Example

```py
import pytest
import capyc.pytest as capy
from rest_framework import status

@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_something(aclient: capy.AsyncClient):
    url = "https://myapi.com/myresource"

    response = await client.get(url, data)
    json = response.json()

    assert json == {...}
    assert response.status_code == status.HTTP_200_OK
```