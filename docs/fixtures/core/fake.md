# fake

Fake instance.

## Example

```py
import capyc.pytest as capy


def test_something(fake: capy.Fake):
    x = fake.slug()
    assert '-' in x
```
