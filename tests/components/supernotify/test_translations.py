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
