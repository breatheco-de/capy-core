# random

Set of utilities for generating random values.

## `seed`

Wrapper of [random.seed](https://docs.python.org/3/library/random.html#random.seed), currently does not working with [Faker](https://faker.readthedocs.io/).

### Example

```py
import random as r
import capyc.pytest as capy


def test_something(random: capy.Random):
    random.seed(1337)
    x = r.randint(0, 100)
    assert x == 79
```

## `tuple` and `args`

Wrapper of [fake.pytuple](https://faker.readthedocs.io/en/master/providers/faker.providers.python.html#faker.providers.python.Provider.pytuple).

### Example

```py
import capyc.pytest as capy


def test_something1(random: capy.Random):
    x = random.tuple(5)
    assert isinstance(x, tuple)
    assert len(x) == 5


def test_something2(random: capy.Random):
    x = random.args(5)
    assert isinstance(x, tuple)
    assert len(x) == 5
```

## `dict` and `kwargs`

Wrapper of [fake.pydict](https://faker.readthedocs.io/en/master/providers/faker.providers.python.html#faker.providers.python.Provider.pydict).

### Example

```py
import capyc.pytest as capy


def test_something1(random: capy.Random):
    x = random.dict(5)
    assert isinstance(x, dict)
    assert len(x) == 5


def test_something2(random: capy.Random):
    x = random.kwargs(5)
    assert isinstance(x, dict)
    assert len(x) == 5
```

## `int`

Wrapper of [random.randint](hhttps://docs.python.org/3/library/random.html#random.randint), defaults `min=0` and `max=1000`.

### Example

```py
import capyc.pytest as capy


def test_something(random: capy.Random):
    x = random.int(10, 100)
    assert isinstance(x, int)
```

## `string`

Build a string that could include each elements specified, default params `size=0`, `lower=False`, `upper=False`, `symbol=False`, `number=False`.

### Example

```py
import capyc.pytest as capy


def test_something(random: capy.Random):
    x = random.int(size=15, lower=True, number=True, symbol=True)
    assert isinstance(x, str)
    assert len(x) == 15
```
