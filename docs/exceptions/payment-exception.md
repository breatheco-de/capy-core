# PaymentException


Exception that represents a payment error.

## Params
- details (`str`): error description.
- slug (`Optional[str]=None`): status code.
- data (`Any=None`): data to be used as context.
- queryset (`Optional[QuerySet]=None`): queryset related to this error.
- silent (`bool=False`): if True, it return a error not showed to the user, and `slug` as `silent_code`.

## Example

```py
from capyc.rest_framework.exceptions import ValidationException
from myapp.models import MyModel


raise ValidationException("my error")
raise ValidationException("my error", slug="my_error")

qs = MyModel.objects.filter(id__in=[...])
raise ValidationException("you cannot access to this resource", queryset=qs, data={"ids": [...]})

raise ValidationException("you cannot access to this resource", slug="bad-resource", silent=True, data={"allowed_resources": [...]})
```
