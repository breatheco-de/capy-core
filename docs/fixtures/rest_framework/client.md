# client

Wrapper of [APIClient](https://www.django-rest-framework.org/api-guide/testing/#apiclient).

## Example

```py
import capyc.pytest as capy
from rest_framework import status


def test_something(client: capy.Client):
    url = "https://myapi.com/myresource"

    response = client.get(url, data)
    json = response.json()

    assert json == {...}
    assert response.status_code == status.HTTP_200_OK
```