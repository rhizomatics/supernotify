from pathlib import Path

import yaml

from custom_components.supernotify.schema import NOTIFY_ACTION_SCHEMA

SERVICES_FILE = Path(__file__).parents[3] / "custom_components" / "supernotify" / "services.yaml"

# Accepted by the schema but deliberately not offered in the UI editor
NOT_IN_UI_EDITOR = {
    "recipients",  # deprecated v2.2.0
}


def _notify_ui_fields() -> set[str]:
    fields = yaml.safe_load(SERVICES_FILE.read_text())["notify"]["fields"]
    flat: set[str] = set()
    for name, spec in fields.items():
        flat |= set(spec["fields"]) if "fields" in spec else {name}
    return flat


def test_notify_schema_fields_all_declared_for_ui_editor():
    """The UI editor drops to raw YAML if a call has any field services.yaml doesn't declare, so
    e.g. an automation still using the legacy `data:` must not lose the visual editor."""
    schema_fields = {str(key) for key in NOTIFY_ACTION_SCHEMA.validators[-1].schema}

    assert schema_fields - NOT_IN_UI_EDITOR - _notify_ui_fields() == set()
