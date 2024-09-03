# Availability

it acts like a feature toggle.

## `feature.availability`

It returns a handler to be used with `feature.add`, the provided function is used with `feature.is_enabled`.

### Availability params

- name (`str`): toggle name.
- frontend (`bool=True`): if true, it could be accessed using an API Rest.
- default (`Optional[bool]=None`): if it returns None, it use this value instead.

### Decorated function params

- **named (`Any`): any argument, any type.

### Example

```py
from capyc.core.managers import feature
from yourapp.models import User


@feature.availability("activity.logs")
def enable_activity() -> bool:
    env = os.getenv("MY_ENV")
    if env in feature.TRUE:
        return True

    if env in feature.FALSE:
        return False


@feature.availability("auth.new_design")
def enable_new_design(user: User) -> bool:
    return user.id % 15 == 0


feature.add(enable_activity, enable_new_design)
```

## `feature.is_enabled`

Get the result of the evaluation of the provided function, if None, get the default provided, else `False`.

### params

- name (`str`): toggle name.
- context (`dict[str, Any]={}`): function arguments.
- default (`Optional[bool]=None`): if it returns None, it use this value instead.

### Example

```py
from capyc.core.managers import feature
from yourapp.models import User


# make sure that flags would have loaded previously.
if feature.is_enabled("activity.logs", default=False):
    ...
else:
    ...

user1 = User.objects.get(id=1)
if feature.is_enabled("auth.new_design", context={'user': user1}):
    ...
else:
    ...

user2 = User.objects.get(id=2)
context = feature.context(user=user2)
if feature.is_enabled("auth.new_design", context=context):
    ...
else:
    ...
```
