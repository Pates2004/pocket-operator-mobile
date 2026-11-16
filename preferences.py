"""Read and atomically persist preferences without discarding musical state."""

import configparser
import os
from pathlib import Path

from app_paths import CONFIG_PATH

LANGUAGES = ("pl", "en")
THEMES = ("system", "light", "dark")


def read_config(path=CONFIG_PATH):
    config = configparser.ConfigParser(interpolation=None)
    if Path(path).exists():
        with Path(path).open(encoding="utf-8") as stream:
            config.read_file(stream)
    return config


def atomic_write(config, path=CONFIG_PATH):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            config.write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def appearance(path=CONFIG_PATH):
    config = read_config(path)
    values = config["INTERFACE"] if config.has_section("INTERFACE") else {}
    language, theme = values.get("language"), values.get("theme")
    complete = (
        values.get("setup_complete") == "true"
        and language in LANGUAGES
        and theme in THEMES
    )
    return language, theme, complete


def save_appearance(language, theme, path=CONFIG_PATH):
    if language not in LANGUAGES or theme not in THEMES:
        raise ValueError("Select a valid language and theme")
    config = read_config(path)
    config["INTERFACE"] = {
        "language": language,
        "theme": theme,
        "setup_complete": "true",
    }
    atomic_write(config, path)
