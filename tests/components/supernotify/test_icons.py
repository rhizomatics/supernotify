import json
import re
from pathlib import Path

COMPONENT_DIR = Path(__file__).parents[3] / "custom_components" / "supernotify"
ICONS = json.loads((COMPONENT_DIR / "icons.json").read_text())
STRINGS = json.loads((COMPONENT_DIR / "strings.json").read_text())

MDI_ICON = re.compile(r"^mdi:[a-z0-9]+(-[a-z0-9]+)*$")
# platforms whose entities are only ever on or off
ON_OFF_PLATFORMS = {"switch", "binary_sensor"}


def test_entity_icons_match_translated_entities():
    """Every entity icon is keyed by a translation_key that strings.json knows, and the reverse"""
    assert set(ICONS["entity"]) == set(STRINGS["entity"])
    for platform, entities in ICONS["entity"].items():
        assert set(entities) == set(STRINGS["entity"][platform]), platform


def test_entity_icons_are_mdi_names():
    for platform, entities in ICONS["entity"].items():
        for key, icons in entities.items():
            assert MDI_ICON.match(icons["default"]), f"{platform}.{key} default"
            for state, icon in icons.get("state", {}).items():
                assert MDI_ICON.match(icon), f"{platform}.{key} state {state}"


def test_on_off_entities_show_when_off():
    """Switches and binary_sensors look different when off, so a disabled scenario, recipient,
    delivery or transport stands out in any entity list, tile or device page"""
    for platform in ON_OFF_PLATFORMS:
        for key, icons in ICONS["entity"][platform].items():
            states = icons.get("state", {})
            assert set(states) <= {"on", "off"}, f"{platform}.{key}"
            assert "off" in states, f"{platform}.{key} has no icon for off"
            assert states["off"] != icons["default"], f"{platform}.{key} off icon is the default icon"
