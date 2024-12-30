__all__ = ["C"]


class C:
    """
    Shortener for a call.

    It'll be used to cover an api exception that returns multiple errors.
    """

    args: tuple
    kwargs: dict

    def __init__(self, *args: tuple, **kwargs: dict):
        self.args = args
        self.kwargs = kwargs


class Filter(C):
    """
    Represents a filter call.
    """

    priority = 2
    pass


class Annotate(C):
    """
    Represents an annotate call.
    """

    priority = 1
    pass


class Aggregate(C):
    """
    Represents an aggregate call.
    """

    priority = 0
    pass
