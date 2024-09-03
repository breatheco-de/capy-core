# queryset

Utils to manage [querysets](https://docs.djangoproject.com/en/5.1/ref/models/querysets/).

## `get_pks`

Get primary keys from a [QuerySet](https://docs.djangoproject.com/en/5.1/ref/models/querysets/).

### example:

```py
import capyc.pytest as capy
from my_app.models import MyModel

def test_something(queryset: capy.QuerySet):
    qs = MyModel.objects.filter()
    x = queryset.get_pks(qs)
    assert x == [1, 2, 3]
```


## `with_pks`

Assert that a [QuerySet](https://docs.djangoproject.com/en/5.1/ref/models/querysets/) contains the following primary keys.

### example:

```py
import capyc.pytest as capy
from my_app.models import MyModel

def test_something(queryset: capy.QuerySet):
    qs = MyModel.objects.filter()
    queryset.with_pks(qs, [1, 2, 3])
```