import logging
import os
from functools import cache
from typing import Optional

__all__ = ["translation"]

IS_TEST_ENV = os.getenv("ENV") == "test"
logger = logging.getLogger(__name__)


def get_short_code(code: str) -> str:
    return code[:2]


def format_and_assert_code(code: str, from_kwargs: bool = False) -> None:
    # do not remove the assertions

    code = code.strip()

    if code == "*":
        return code  # Allow wildcard as a valid "code"

    is_short = len(code) == 2

    # first two character only with lowercase
    if not code[:2].islower():
        raise ValueError("Lang code is not lowercase")

    # last two character only with lowercase
    if not is_short and from_kwargs and not code[3:].islower():
        raise ValueError("Country code is not lowercase")

    # last two character only with uppercase
    elif not is_short and not from_kwargs and not code[2:].isupper():
        raise ValueError("Country code is not uppercase")

    separator = "_" if from_kwargs else "-"

    # the format is en or en-US
    if not (len(code) == 2 or (len(code) == 5 and code[2] == separator)):
        raise ValueError("Code malformed")

    if not from_kwargs:
        return code.replace(separator, "_")

    return code


def format_languages(code: str) -> list:
    """Translate the language to the local language."""

    languages = set()

    code.replace(" ", "")

    codes = [x for x in code.split(",") if x]

    for code in codes:
        priority = 1
        if ";q=" in code:
            s = code.split(";q=")
            code = s[0]
            try:
                priority = float(s[1])
            except Exception:
                raise ValueError(
                    'The priority is not a float, example: "en;q=0.5"', slug="malformed-quantity-language-code"
                )

        languages.add((priority, code))

    print("languages", languages)
    return [x[1] for x in sorted(languages, key=lambda x: (x[0], "-" in x[1], x[1]), reverse=True)]


def try_to_translate(code, **kwargs: str) -> str | None:
    is_short = len(code) == 2

    if code.lower() in kwargs:
        return kwargs[code.lower()]

    short_code = get_short_code(code)
    if not is_short and short_code in kwargs:
        return kwargs[short_code]

    if not is_short:
        for x in kwargs.keys():
            if x.startswith(short_code):
                return kwargs[x]

    print("is_short", is_short, code, get_short_code(code))

    return None


@cache
def translation(code: Optional[str] = "en", slug: Optional[str] = None, **kwargs: str) -> str:
    """Get the translation."""

    if not code:
        code = "en"

    asked_languages = format_languages(code)
    print(asked_languages)
    languages = [format_and_assert_code(language) for language in asked_languages]

    # do the assertions
    for key in kwargs:
        format_and_assert_code(key, from_kwargs=True)

    # the english if mandatory
    if not ("en" in kwargs or "en_us" in kwargs):
        raise ValueError("The english translation is mandatory")

    if slug and IS_TEST_ENV:
        return slug

    for language in languages:
        v = try_to_translate(language, **kwargs)

        if v:
            return v

    if "en_us" in kwargs:
        return kwargs["en_us"]

    return kwargs["en"]
