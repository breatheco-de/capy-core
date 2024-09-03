# Setup

Add our exception handler in your `settings.py`.

```py
REST_FRAMEWORK = {
    ...
    "EXCEPTION_HANDLER": "capyc.rest_framework.exception_handler.exception_handler",
    ...
}
```