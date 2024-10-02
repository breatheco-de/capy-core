# Reading Flags

You could access flags in your code using the `feature.flags` property.

```py
from capyc.core.managers import feature


flags = feature.flags
```

## `feature.flags.get`

You could read flags in your code using the `feature.flags.get` method, it could return a `str` or `None` if not exists.

```py
from capyc.core.managers import feature

flags = feature.flags

flags.get("FEATURE_A")
```
