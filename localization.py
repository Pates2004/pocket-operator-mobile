"""UTF-8 .lng catalogs, including templates for legacy runtime messages."""

import json
import re
import string

from app_paths import LANG_DIR

_language = "pl"
_catalogs = {}
_patterns = {}


def load_catalog(language):
    if language not in {"pl", "en"}:
        raise ValueError("Unsupported language")
    if language not in _catalogs:
        with (LANG_DIR / f"{language}.lng").open(encoding="utf-8") as stream:
            catalog = json.load(stream)
        if catalog.get("language") != language:
            raise ValueError("Invalid language catalog")
        _catalogs[language] = catalog["strings"]
        patterns = []
        for source, target in catalog["strings"].items():
            if "{" not in source:
                continue
            parts = []
            for literal, field, _, _ in string.Formatter().parse(source):
                parts.append(re.escape(literal))
                if field is not None:
                    parts.append(f"(?P<{field}>.+?)")
            patterns.append((re.compile("^" + "".join(parts) + "$", re.S), target))
        _patterns[language] = patterns
    return _catalogs[language]


def set_language(language):
    global _language
    load_catalog(language)
    _language = language


def get_language():
    return _language


def tr(text, **values):
    text = str(text)
    catalog = load_catalog(_language)
    if text in catalog:
        return catalog[text].format(**values) if values else catalog[text]
    if values:
        return text.format(**values)
    for pattern, target in _patterns[_language]:
        match = pattern.fullmatch(text)
        if match:
            return target.format(
                **{key: tr(value) for key, value in match.groupdict().items()}
            )
    if "\t" in text:
        label, shortcut = text.split("\t", 1)
        return tr(label) + "\t" + shortcut
    return text
