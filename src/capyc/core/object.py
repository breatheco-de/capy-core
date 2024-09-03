from typing import Any

__all__ = ["Object"]



class Object(dict):
    """Support use a dict like a javascript object."""

    def __init__(self, **kwargs: Any):
        dict.__init__(self, **kwargs)

    @classmethod
    def from_mapping(cls, mapping: dict) -> "Object":
        return cls(**mapping)

    def __setattr__(self, name: str, value: Any):
        self[name] = value

    def __getattr__(self, name: str) -> Any:
        return self[name]
