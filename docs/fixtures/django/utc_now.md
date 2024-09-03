# utc_now

`datetime.now` fixture shortcut.

## example:

```py
import time
import capyc.pytest as capy
from my_app.models import MyModel
from django.utils import timezone
from datetime import datetime


def test_something(utc_now: datetime):
    d1 = timezone.now()
    time.sleep(5)
    d2 = timezone.now()
    d3 = datetime.now() # it's not mockable
    assert utc_now == d1
    assert utc_now == d2
    assert utc_now != d3
```
