from datetime import datetime
from typing import Any

import pytz


__all__ = ["argument_parser"]

list_of_args = list[tuple[int, dict[str, Any]]]
args = list[tuple[int, dict[str, Any]]]


def argument_fixer(arg: dict) -> Any:
    for key in arg:
        if isinstance(arg[key], datetime):
            if arg[key].tzinfo is None:
                arg[key] = arg[key].replace(tzinfo=pytz.utc)
    return arg


def integer_parser(arg: int) -> args:
    return (arg, dict())


def dict_parser(arg: int) -> args:
    return (1, argument_fixer(arg or dict()))


def boolean_parser(arg: int) -> args:
    return (1, dict())


def tuple_parser(arg: tuple[Any, Any]) -> list_of_args:
    if len(arg) != 2:
        raise ValueError("arg must be a tuple of two elements")

    if isinstance(arg[0], int) and isinstance(arg[1], dict):
        return (arg[0], argument_fixer(arg[1] or dict()))

    if isinstance(arg[0], int) and isinstance(arg[1], dict):
        return (arg[1], argument_fixer(arg[0] or dict()))

    raise ValueError(f"The tuple[{arg[0].__class__.__name__}, {arg[0].__class__.__name__}] is invalid")


def list_parser(arg: int) -> list_of_args:
    result = []
    for item in arg:
        if isinstance(item, dict):
            result.append(dict_parser(item))
            continue

        if isinstance(item, tuple):
            result.append(tuple_parser(item))
            continue

        raise ValueError(f"You can't pass a list of {arg.__class__.__name__} as argument")

    return result


def argument_parser(arg: Any) -> list_of_args:
    if isinstance(arg, tuple):
        return [tuple_parser(arg)]

    if isinstance(arg, list):
        return list_parser(arg)

    if isinstance(arg, dict):
        return [dict_parser(arg)]

    if isinstance(arg, bool):
        return [boolean_parser(arg)]

    if isinstance(arg, int):
        return [integer_parser(arg)]

    print(f"The argument parser has a receive a invalid type {arg.__class__.__name__}")
    return []
