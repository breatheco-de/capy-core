"""
DateTime fixtures.
"""

from datetime import datetime as dt
from typing import Any, Generator, Optional, final

import pytest
from django.utils import timezone

__all__ = ["DateTime", "datetime"]


@final
class DateTime:
    """
    QuerySet utils.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch

    def now(self) -> None:
        """
        Get current datetime.

        Usage:

        ```py
        datetime.now()
        ```
        """

        d = timezone.now()
        self.set(d)

        return d

    def set(self, new_datetime: Optional[dt] = None) -> list[Any]:
        """
        Set current datetime.

        Usage:

        ```py
        from django.utils import timezone
        mydt = timezone.now()
        datetime.set(mydt)
        ```
        """
        if new_datetime is None:
            new_datetime = timezone.now()

        self._monkeypatch.setattr(timezone, "now", lambda: new_datetime)


@pytest.fixture()
def datetime(monkeypatch: pytest.MonkeyPatch) -> Generator[DateTime, None, None]:
    """
    Datetime utils.
    """

    yield DateTime(monkeypatch)
