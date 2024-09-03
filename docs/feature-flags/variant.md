# Variant

it acts like a feature toggle.

## `feature.variant`

It returns a handler to be used with `feature.add`, the provided function is used with `feature.get_variant`.

### Variant params

- name (`str`): toggle name.
- frontend (`bool=True`): if true, it could be accessed using an API Rest.
- default (`Optional[str]=None`): if it returns None, it uses this value instead.

### Decorated function params

- **named (`Any`): any argument, any type.

### Example

```py
from capyc.core.managers import feature
from yourapp.models import User


@feature.variant("admissions.academy.brand-color")
def brand_color() -> bool:
    return os.getenv("BRAND_COLOR")


@feature.variant("auth.alert-color")
def alert_color(user: User) -> bool:
    if  user.id % 15 == 0:
        return "VIOLET"

    if "@gmail" in user.email:
        return "ORANGE"

    return "YELLOW"


feature.add(brand_color, alert_color)
```

## `feature.get_variant`

Get the result of the evaluation of the provided function, if None, get the default provided, else `unknown`.

### params

- name (`str`): toggle name.
- context (`dict[str, Any]={}`): function arguments.
- default (`Optional[str]=None`): if it returns None, it uses this value instead.

### Example

```py
from capyc.core.managers import feature
from yourapp.models import User


# make sure that flags have been loaded previously.
variant1 = feature.get_variant("admissions.academy.brand-color", default="BLUE")

user1 = User.objects.get(id=1)
variant2 = feature.get_variant("auth.alert-color", context={'user': user1})

user2 = User.objects.get(id=2)
context = feature.context(user=user2)
variant3 = feature.get_variant("auth.alert-color", context=context)
```
