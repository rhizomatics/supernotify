"""Common `options:` tuning keys and their metadata — documentation/introspection only.

Does not replace or drive runtime validation (schema.py's CONF_OPTIONS stays a
permissive `dict`). Keys and their value-domain constants live here, alongside the
metadata that describes them - never redeclared elsewhere.

Common options (read centrally in envelope.py/delivery.py, applicable to every
transport) are declared below. Transport-specific options and their own key/value
constants are declared on the owning Transport subclass's `declared_options` (see
transport.py) and in that transport's own module - not here, to avoid this module
importing static_config/engine and creating a cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from custom_components.supernotify.model import SelectionRule

OPTION_SIMPLIFY_TEXT = "simplify_text"
OPTION_STRIP_URLS = "strip_urls"
OPTION_MESSAGE_USAGE = "message_usage"
OPTION_TARGET_CATEGORIES = "target_categories"
OPTION_UNIQUE_TARGETS = "unique_targets"
OPTION_TARGET_SELECT = "target_select"
# how area_id/floor_id/label_id targets are handled for a delivery
OPTION_TARGET_SELECTORS = "target_selectors"
TARGET_SELECTORS_AUTO = "auto"  # discover from the action description whether selectors pass through
TARGET_SELECTORS_NATIVE = "native"  # pass selectors through to the underlying action untouched
TARGET_SELECTORS_RESOLVE = "resolve"  # resolve selectors to entity_ids within supernotify
TARGET_SELECTORS_VALUES = [TARGET_SELECTORS_AUTO, TARGET_SELECTORS_NATIVE, TARGET_SELECTORS_RESOLVE]
OPTION_DATA_KEYS_SELECT = "data_keys_select"
OPTION_DEVICE_DOMAIN = "device_domain"
OPTION_DEVICE_MODEL_SELECT = "device_model_select"
OPTION_DEVICE_MANUFACTURER_SELECT = "device_manufacturer_select"
OPTION_DEVICE_OS_SELECT = "device_os_select"
OPTION_DEVICE_LABEL_SELECT = "device_label_select"
OPTION_DEVICE_AREA_SELECT = "device_area_select"
OPTION_DEVICE_DISCOVERY = "device_discovery"
OPTION_JPEG = "jpeg_opts"
OPTION_PNG = "png_opts"
MEDIA_OPTION_REPROCESS = "reprocess"

# Domain of a SelectionRule-typed option's mapping, e.g. {SELECT_INCLUDE: [...], SELECT_EXCLUDE: [...]}
SELECT_INCLUDE = "include"
SELECT_EXCLUDE = "exclude"

# Deprecated v1.9.0 aliases, upgraded in Delivery.upgrade_deprecations() - not part of
# COMMON_OPTIONS since they're not offered to new configuration.
OPTION_TARGET_INCLUDE_RE = "target_include_re"
OPTION_DATA_KEYS_INCLUDE_RE = "data_keys_include_re"
OPTION_DATA_KEYS_EXCLUDE_RE = "data_keys_exclude_re"


@dataclass(frozen=True)
class DeliveryOption:
    key: str
    description: str
    value_type: Callable[..., object] = cv.string
    examples: list[str] | None = None


COMMON_OPTIONS: list[DeliveryOption] = [
    DeliveryOption(
        OPTION_SIMPLIFY_TEXT,
        "Remove some common symbols that can trip up voice assistants. SSML markup is left alone on spoken transports",
        value_type=cv.boolean,
    ),
    DeliveryOption(OPTION_STRIP_URLS, "Remove URLs from message and title", value_type=cv.boolean),
    DeliveryOption(OPTION_MESSAGE_USAGE, "Combine message and title, default title", examples=["combine_title", "use_title"]),
    DeliveryOption(
        OPTION_TARGET_SELECT,
        "Only use targets fully matching these regular expressions",
        value_type=SelectionRule,
    ),
    DeliveryOption(
        OPTION_TARGET_SELECTORS,
        "How area, floor and label targets are handled",
        value_type=vol.In({
            TARGET_SELECTORS_AUTO: "Pass through if the action accepts a target selector, otherwise resolve",
            TARGET_SELECTORS_NATIVE: "Always pass through to the action untouched",
            TARGET_SELECTORS_RESOLVE: "Resolve to entity_ids within Supernotify",
        }),
    ),
    DeliveryOption(
        OPTION_UNIQUE_TARGETS,
        "Don't pass targets already used in this notification",
        value_type=cv.boolean,
    ),
    DeliveryOption(
        OPTION_TARGET_CATEGORIES,
        "Which targets to pass, e.g. entity_id, email, device_id",
        value_type=list,
        examples=['["entity_id", "device_id"]'],
    ),
    DeliveryOption(OPTION_DEVICE_DISCOVERY, "Switch automatic device discovery on or off", value_type=cv.boolean),
    DeliveryOption(OPTION_DEVICE_DOMAIN, "One or more Home Assistant domains to discover devices, e.g. alexa_devices"),
    DeliveryOption(OPTION_DEVICE_MODEL_SELECT, "Choose device models in device discovery", value_type=SelectionRule),
    DeliveryOption(
        OPTION_DEVICE_MANUFACTURER_SELECT,
        "Choose device manufacturers in device discovery",
        value_type=SelectionRule,
    ),
    DeliveryOption(
        OPTION_DEVICE_OS_SELECT,
        "Choose device operating systems in device discovery",
        value_type=SelectionRule,
    ),
    DeliveryOption(OPTION_DEVICE_LABEL_SELECT, "Choose devices by label in device discovery", value_type=SelectionRule),
    DeliveryOption(
        OPTION_DEVICE_AREA_SELECT,
        "Choose devices by Home Assistant area in device discovery",
        value_type=SelectionRule,
    ),
]

# Only meaningful for transports that call Envelope.grab_image() - not read at all otherwise,
# so not universal like COMMON_OPTIONS. Transports splice this into their own declared_options.
MEDIA_OPTIONS: list[DeliveryOption] = [
    DeliveryOption(
        OPTION_JPEG,
        "Tune camera snapshot grabs saved/attached as JPEG",
        value_type=dict,
        examples=["progressive: true", "optimize: true", "quality: 50"],
    ),
    DeliveryOption(
        OPTION_PNG, "Tune camera snapshot grabs saved/attached as PNG", value_type=dict, examples=["optimize: true"]
    ),
    DeliveryOption(
        MEDIA_OPTION_REPROCESS,
        "Whether to regenerate a camera snapshot already grabbed for this notification",
        value_type=vol.In({
            "always": "Always regenerate",
            "never": "Reuse the existing grab",
            "preserve": "Keep the original file",
        }),
    ),
]


def all_options_for(transport_options: list[DeliveryOption]) -> list[DeliveryOption]:
    """Common options plus a transport's own — the full applicable set for one transport."""
    return [*COMMON_OPTIONS, *transport_options]
