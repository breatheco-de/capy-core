# Setup

Add our exception handler in your `settings.py`.

```py
REST_FRAMEWORK = {
    ...
    "EXCEPTION_HANDLER": "capyc.rest_framework.exception_handler.exception_handler",
    ...
}
```

And this to your `conftest.py`.

```py
pytest_plugins = (
    "capyc.pytest.core",
    "capyc.pytest.newrelic",
    "capyc.pytest.django",
    "capyc.pytest.rest_framework",
    "capyc.pytest.circuitbreaker",
)
```