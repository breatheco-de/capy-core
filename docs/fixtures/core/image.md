# image

Set of utilities for formatting values.

## `random`

Generate a random .png file and return the [file object](https://www.w3schools.com/python/python_file_open.asp).

### Example

```py
import capyc.pytest as capy


def test_something(image: capy.Image):
    f = image.random(qs)
    content = f.read()
    ...
```
