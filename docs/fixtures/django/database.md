# database

Utils to manage the database like [Mixer](https://mixer.readthedocs.io/en/latest/quickstart.html) does.

## `get_model`

Get model using a path.

### example:

```py
import capyc.pytest as capy


def test_something(database: capy.Database):
    MyModel = database.get_model('myapp.MyModel')
```

## `create`

Create model instances like [Mixer](https://mixer.readthedocs.io/en/latest/quickstart.html) does.

### Status

Release cantidate.

### Arguments

#### Format

It must be model_name or app__model_name.

#### Value

- number: number of elements to be created.
- dict: attributes of the object to be created.
- tuple(number, dict): number of elements to be created and atributes that it must have.
- list(dict, dict, ...): create a object per dict in the list with the following properties.

#### Relationships

- Each model related to a model that requires other models, and it cannot be black or null, it will be created automatically.
- To manage a relation to one model use `{"my_rel_id": 7}`.
- To manage a relation to many models use `{"my_rels": [7, 8, 9]}`.

### example:

```py
import capyc.pytest as capy
from inferredapp.models import MyModel
from myapp1.models import MyModel2 as App1MyModel2
from myapp2.models import MyModel2 as App2MyModel2
from myapp3.models import MyModel1, MyModel3, MyModel4, MyModel5, MyModel6


def test_something1(database: capy.Database):
    model = database.create(
        my_model=1, # inferred the app, and create one MyModel instance
        myapp1__my_model2=1, # create one 'myapp1.MyModel2' instance
        myapp2__my_model2=1, # create one 'myapp2.MyModel2' instance
    )
    assert model.keys() == ['my_model', 'myapp1__my_model2', 'myapp2__my_model2']
    assert isinstance(model.my_model, MyModel)
    assert isinstance(model.myapp1__my_model2, App1MyModel2)
    assert isinstance(model.myapp2__my_model2, App2MyModel2)


def test_something2(database: capy.Database):
    model = database.create(
        my_model1=2, # create 2 instances of MyModel1
        my_model3={'my_attr': 'my_value'}, # create one instance of MyModel3 and set `my_attr` to `my_value`
        my_model4=(2, {'my_attr': 'my_value'}), # create two instances of MyModel4 and set `my_attr` to `my_value`
        my_model5={'my_model_id': 1}, # create one instance of MyModel5 and set the relation of my_model to MyModel
        my_model6={'my_models': [1]}, # create one instance of MyModel6 and set the m2m relations of my_models to [MyModel]
    )
    assert model.keys() == ['my_model', 'my_model1', 'my_model3', 'my_model4', 'my_model5', 'my_model6']
    assert isinstance(model.my_model, MyModel)

    assert len(model.my_model1) == 2
    assert all([isinstance(x, MyModel1) for x in model.my_model1])

    assert isinstance(model.my_model3, MyModel3)

    assert len(model.my_model4) == 2
    assert all([isinstance(x, MyModel4) and x.my_attr == 'my_value' for x in model.my_model4])

    assert isinstance(model.my_model5, MyModel5)
    assert model.my_model5.id == model.my_model.id

    assert isinstance(model.my_model6, MyModel6)
    assert all([x.id == model.my_model.id for x in model.my_model6.my_models.all()])
```

## `acreate`

Async wrapper of `create`.

### Example:

```py
import pytest
import capyc.pytest as capy


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_something(aclient: capy.AsyncClient):
    model = await database.acreate(...)
```

## `list_of`

Get list of instances of a model.

### example:

```py
def test_something1(database: capy.Database):
    ...
    assert database.list_of('myapp.MyModel') == [
        {
            'my_attr1': 'my_value1',
            'my_attr2': 'my_value2',
        }
    ]
```


## `alist_of`

Get list of instances of a model.

### example:

```py
import pytest
import capyc.pytest as capy


@pytest.mark.asyncio
@pytest.mark.django_db(reset_sequences=True)
async def test_something1(database: capy.Database):
    ...
    assert await database.alist_of('myapp.MyModel') == [
        {
            'my_attr1': 'my_value1',
            'my_attr2': 'my_value2',
        }
    ]
```