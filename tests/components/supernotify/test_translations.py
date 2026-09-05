import json
from pathlib import Path

COMPONENT_DIR = Path(__file__).parents[3] / "custom_components" / "supernotify"
TRANSLATIONS_DIR = COMPONENT_DIR / "translations"
STRINGS_FILE = COMPONENT_DIR / "strings.json"


def _leaf_keys(obj: dict, prefix: str = "") -> set[str]:
    """Return dot-separated paths for every leaf value in a nested dict."""
    keys: set[str] = set()
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= _leaf_keys(v, path)
        else:
            keys.add(path)
    return keys


def _leaf_values(obj: dict, prefix: str = "") -> dict[str, str]:
    """Return dot-separated path -> value for every leaf value in a nested dict."""
    values: dict[str, str] = {}
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            values.update(_leaf_values(v, path))
        else:
            values[path] = v
    return values


# Keys where a non-English translation is expected to be identical to English in every
# language - the "Supernotify" brand name, and the MQTT protocol name (not translated).
EXPECTED_IDENTICAL_IN_EVERY_LANGUAGE = {
    "title",
    "options.step.archive.sections.mqtt.name",
}

# (translation file stem, dot-separated key) pairs where a specific language's word for
# something genuinely happens to be spelled the same as English (a true cognate/loanword),
# rather than a forgotten translation.
EXPECTED_IDENTICAL_TO_ENGLISH = {
    ("de", "config.step.user.data.name"),  # "Name" is also the German word for name
    ("de", "config.step.reconfigure.data.name"),
    ("es", "selector.outcome_selection.options.error"),  # "Error" is the Spanish word too
    ("it", "options.step.archive.sections.file.name"),  # "File" is a standard Italian loanword
    ("de", "services.notify.fields.debug.name"),  # "Debug" is a standard German tech loanword
    ("it", "services.notify.fields.debug.name"),  # "Debug" is a standard Italian tech loanword
    ("nl", "services.notify.fields.debug.name"),  # "Debug" is a standard Dutch tech loanword
    ("it", "services.notify.fields.media.name"),  # "Media" is also the Italian word for media
    ("nl", "services.notify.fields.media.name"),  # "Media" is also the Dutch word for media
    ("fr", "services.notify.fields.message.name"),  # "Message" is also the French word for message
    ("fr", "services.notify.fields.actions.name"),  # "Actions" is also the French word for actions
}


def test_non_english_translations_differ_from_english():
    """Every translated value should actually be translated - a value identical to the
    English source is almost always a forgotten or copy-pasted string, not a real
    translation (see the legacy_yaml_config repair strings, which stayed in English in
    every language until this was caught)."""
    english = _leaf_values(json.loads((TRANSLATIONS_DIR / "en.json").read_text()))

    for path in TRANSLATIONS_DIR.glob("*.json"):
        if path.stem == "en":
            continue
        translated = _leaf_values(json.loads(path.read_text()))

        untranslated = [
            key
            for key, value in translated.items()
            if key in english
            and value == english[key]
            and key not in EXPECTED_IDENTICAL_IN_EVERY_LANGUAGE
            and (path.stem, key) not in EXPECTED_IDENTICAL_TO_ENGLISH
        ]
        assert not untranslated, f"{path.name} has untranslated (English) values for: {sorted(untranslated)}"


def test_all_translations_match_strings():
    strings = json.loads(STRINGS_FILE.read_text())
    expected_keys = _leaf_keys(strings)

    translation_files = list(TRANSLATIONS_DIR.glob("*.json"))
    assert translation_files, "No translation files found"

    for path in translation_files:
        translation = json.loads(path.read_text())
        actual_keys = _leaf_keys(translation)
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        assert not missing, f"{path.name} is missing keys: {sorted(missing)}"
        assert not extra, f"{path.name} has unexpected keys: {sorted(extra)}"
