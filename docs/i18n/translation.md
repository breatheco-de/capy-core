# translation

Get translation from the following options, default to english.

## Params

- code (`str`): language code, it accepts the `ACCEPT` header value.
- **translation (`str`): list of translations, `en-US` is `en_us`
- slug (`Optional[str]=None`): if it was provided, return the slug if the environment is test.

## Example:

```py
from capyc.core.i18n import translation


lang = ...
translated1 = translation(lang, en="my text", es="mi texto")
translated1 = translation(lang, en="my text", es="mi texto", slug="my-text")
translated3 = translation(
    lang,
    en_us="we cannot pronounce the T's",
    en_uk="we cannot pronounce the R's",
)
```
