import logging
import os
from functools import cache, lru_cache
from typing import Optional

from langcodes import Language

__all__ = ["translation"]

IS_TEST_ENV = os.getenv("ENV") == "test"
logger = logging.getLogger(__name__)


def get_short_code(code: str) -> str:
    return code[:2]


def sort_accept_languages(code: str) -> list:
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

    return None


@lru_cache(maxsize=20)
def validate_lang_code(code: str, argument: bool = False) -> None:
    code = code.strip()

    if argument:
        for x in code:
            if x != "_" and x.isupper():
                raise ValueError(f"Invalid argument {code}, lowercase is mandatory")

    elif code == "*":
        return

    if Language.get(code).is_valid() is False:
        raise ValueError(f"Invalid language code {code}")


@lru_cache(maxsize=20)
def get_serialized_lang_code(code: str) -> None:
    code = code.strip()

    if code == "*":
        return code

    validate_lang_code(code)

    return code.replace("-", "_").lower()


@cache
def translation(code: Optional[str] = "en", slug: Optional[str] = None, **kwargs: str) -> str:
    """Get the translation."""

    if not code:
        code = "en"

    # sort Accept-Language value
    asked_languages = sort_accept_languages(code)

    # serialize Accept-Language options
    languages = [get_serialized_lang_code(language) for language in asked_languages]

    # do the assertions over the translations provided
    for key in kwargs:
        validate_lang_code(key, argument=True)

    # ask for english translation
    if not ("en" in kwargs or "en_us" in kwargs):
        raise ValueError("English translation is mandatory")

    # you can return a code instead of a translation
    if slug and IS_TEST_ENV:
        return slug

    # try to find a translation for the asked languages
    for language in languages:
        v = try_to_translate(language, **kwargs)

        if v:
            return v

    # get the english translation
    if "en_us" in kwargs:
        return kwargs["en_us"]

    return kwargs["en"]
