# datetime

Utils and shortcuts to manage [datetime](https://docs.python.org/3/library/datetime.html) with [`timezone.now`](https://docs.djangoproject.com/en/5.1/topics/i18n/timezones/#naive-and-aware-datetime-objects).

## `now`

Wrapper to [`timezone.now`](https://docs.djangoproject.com/en/5.1/topics/i18n/timezones/#naive-and-aware-datetime-objects), also frozen the current time using `set` method.

### example:

```py
import time
import capyc.pytest as capy
from my_app.models import MyModel
from django.utils import timezone
from datetime import datetime as dt


def test_something(datetime: capy.DateTime):
    d1 = datetime.now()
    time.sleep(5)
    d2 = datetime.now()
    d3 = timezone.now()
    d4 = dt.now() # it's not mockable
    assert d1 == d2
    assert d1 == d3
    assert d1 != d4
```


## `set`

Frozen and set [`timezone.now`](https://docs.djangoproject.com/en/5.1/topics/i18n/timezones/#naive-and-aware-datetime-objects) result.

### example:

```py
import time
import capyc.pytest as capy
from my_app.models import MyModel
from django.utils import timezone
from datetime import datetime as dt


def test_something1(datetime: capy.DateTime):
    original = timezone.now()
    datetime.set(original)

    d1 = datetime.now()
    time.sleep(5)
    d2 = datetime.now()
    d3 = timezone.now()
    d4 = dt.now() # it's not mockable
    assert d1 == original
    assert d1 == d2
    assert d1 == d3
    assert d1 != d4


def test_something2(datetime: capy.DateTime):
    datetime.set() # frozen now

    d1 = datetime.now()
    time.sleep(5)
    d2 = datetime.now()
    d3 = timezone.now()
    d4 = dt.now() # it's not mockable
    assert d1 == d2
    assert d1 == d3
    assert d1 != d4
```