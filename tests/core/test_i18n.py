import pytest

from capyc.core.i18n import translation


class TestTranslation:
    def test_wildcard_lang__invalid_lang(self) -> None:
        lang = "*"
        with pytest.raises(ValueError, match="Invalid language code xz"):
            translation(lang, xz="aaaaa")

    def test_wildcard_lang__en_not_provided(self) -> None:
        lang = "*"
        with pytest.raises(ValueError, match="English translation is mandatory"):
            translation(lang, es="aaaaa")

    @pytest.mark.parametrize(
        "lang, chose, translations",
        [
            (
                "*",
                "en",
                {"en": "aaaaa", "fr": "bbbbb", "de": "ccccc"},
            ),
            (
                "*",
                "en_us",
                {"en_us": "aaaaa", "fr": "bbbbb", "de": "ccccc"},
            ),
            (
                "fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7, *;q=0.5",
                "fr",
                {"en": "aaaaa", "fr": "bbbbb", "de": "ccccc"},
            ),
            (
                "fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7, *;q=0.5",
                "fr_ch",
                {"en": "aaaaa", "fr": "bbbbb", "de": "ccccc", "fr_aa": "ddddd", "fr_ch": "eeeee"},
            ),
            (
                "fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7, *;q=0.5",
                "fr",
                {"en": "aaaaa", "fr": "bbbbb", "de": "ccccc", "fr_aa": "ddddd"},
            ),
            (
                "en-US,en;q=0.9,es-419;q=0.8,es;q=0.7",
                "en",
                {"en": "aaaaa", "de": "bbbbb", "fr_aa": "ccccc"},
            ),
        ],
    )
    def test_translate(self, lang: str, chose: str, translations: dict[str, str]) -> None:
        value = translation(lang, **translations)
        assert value == translations[chose]
