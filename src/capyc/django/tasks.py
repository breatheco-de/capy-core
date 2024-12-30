import importlib
from typing import Type

from celery import shared_task
from django.test import RequestFactory

from capyc.core.shorteners import Aggregate, Annotate, Filter
from capyc.django.serializer import Serializer


@shared_task
def revalidate_cache(key: str):
    raise NotImplementedError("revalidate is not implemented")

    parts = key.split(".")
    module = ".".join(parts[:-1])
    serializer_name = ".".join(parts[-1:])

    importlib.import_module(module)
    encodings = ["gzip", "br", "deflate", "zstd"]

    serializer_cls: Type[Serializer] = getattr(module, serializer_name)

    serializer = serializer_cls(request=request)

    params = serializer.generateStaticParams()

    for encoding in encodings:
        factory = RequestFactory()
        request = factory.get(
            "/xyz?sets=extra,lists",
            headers={
                "Cache-Control": "no-cache",
                "Accept": "application/json",
                "Accept-Language": "en",
                "Accept-Encoding": encoding,
            },
        )

        serializer = serializer_cls(request=request)

        params = serializer.revalidate()

        for calls in params:
            if isinstance(calls, list):
                if any(isinstance(call, Annotate) for call in calls):
                    continue
                if any(isinstance(call, Aggregate) for call in calls):
                    continue

            elif isinstance(calls, Annotate):
                continue
            elif isinstance(calls, Aggregate):
                continue
            elif isinstance(calls, Filter):
                pass
