# ValidationException

Exception that represents a generic HTTP error.

## Params
- details (`str`): error description.
- code (`int=400`): status code.
- slug (`Optional[str]=None`): status code.
- data (`Any=None`): data to be used as context.
- queryset (`Optional[QuerySet]=None`): queryset related to this error.
- silent (`bool=False`): if True, it returns an error not shown to the user, and `slug` as `silent_code`.

## Example

```py
from capyc.rest_framework.exceptions import ValidationException
from myapp.models import MyModel


raise ValidationException("my error")
raise ValidationException("not found", code=404)
raise ValidationException("not found", code=404, slug="not-found")

qs = MyModel.objects.filter(id__in=[...])
raise ValidationException("deletion are not allowed", code=409, queryset=qs, data={"ids": [...]})

raise ValidationException("bad type", slug="bad-type", silent=True, data={"allowed_types": [...]})
```
