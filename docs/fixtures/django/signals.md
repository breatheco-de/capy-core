# signals

Utils to manage [signals](https://docs.djangoproject.com/en/5.1/topics/signals/).

## `disable`

Avoid to call [signals](https://docs.djangoproject.com/en/5.1/topics/signals/).

## `enable`

Enable the following [signals](https://docs.djangoproject.com/en/5.1/topics/signals/).

### example:

```py
import capyc.pytest as capy


def test_something(signals: capy.Signals):
    signals.enable('path.to.my.signal1', 'path.to.my.signal2', ...)
```