# format

Set of utilities for formatting values.

## `to_obj_repr`

Transform a [Django](https://docs.djangoproject.com/) [QuerySet](https://docs.djangoproject.com/en/5.1/ref/models/querysets/) and an object in a `list` or `dict`.

### Example

```py
import capyc.pytest as capy
from my_app.models import MyModel


def test_something1(format: capy.Format):
    qs = MyModel.objects.filter()
    x = format.to_obj_repr(qs)
    assert isinstance(x, list)


def test_something2(format: capy.Format):
    obj = MyModel.objects.filter().first()
    x = format.to_obj_repr(obj)
    assert isinstance(x, dict)
```
