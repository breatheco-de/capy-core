from __future__ import absolute_import, unicode_literals

from celery import Celery


app = Celery(task_always_eager=True)



pytest_plugins = ("capyc.pytest.rest_framework",)

