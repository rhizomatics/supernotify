"""The Supernotify integration"""

import re
from collections.abc import Callable
from enum import StrEnum

import voluptuous as vol
from homeassistant.components.notify import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_DEBUG,
    CONF_DESCRIPTION,
    CONF_DOMAIN,
    CONF_EMAIL,
    CONF_ENABLED,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_TARGET,
    CONF_URL,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import TemplateVarsType

from custom_components.supernotify import MEDIA_DIR, TEMPLATE_DIR

from .const import (
    ATTR_ACTION,
    ATTR_ACTION_CATEGORY,
    ATTR_ACTION_GROUPS,
    ATTR_ACTION_URL,
    ATTR_ACTION_URL_TITLE,
    ATTR_ACTIONS,
    ATTR_DATA,
    ATTR_DEBUG,
    ATTR_DELIVERY,
    ATTR_DELIVERY_SELECTION,
    ATTR_DUPE_POLICY_MTSLP,
    ATTR_DUPE_POLICY_NONE,
    ATTR_EMAIL,
    ATTR_JPEG_OPTS,
    ATTR_MEDIA,
    ATTR_MEDIA_CAMERA_DELAY,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CAMERA_PTZ_PRESET,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_MESSAGE_HTML,
    ATTR_MOBILE_APP_ID,
    ATTR_PERSON_ID,
    ATTR_PHONE,
    ATTR_PNG_OPTS,
    ATTR_PRIORITY,
    ATTR_RECIPIENTS,
    ATTR_SCENARIOS_APPLY,
    ATTR_SCENARIOS_CONSTRAIN,
    ATTR_SCENARIOS_REQUIRE,
    ATTR_TIMESTAMP,
    ATTR_TITLE,
    CONF_ACTION_GROUP_NAMES,
    CONF_ACTION_GROUPS,
    CONF_ACTION_TEMPLATE,
    CONF_ALT_CAMERA,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_ARCHIVE_PURGE_INTERVAL,
    CONF_CAMERA,
    CONF_CAMERAS,
    CONF_CLASS,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_DEVICE_MODEL_EXCLUDE,
    CONF_DEVICE_MODEL_INCLUDE,
    CONF_DEVICE_TRACKER,
    CONF_DUPE_CHECK,
    CONF_DUPE_POLICY,
    CONF_DURATION,
    CONF_HOUSEKEEPING,
    CONF_HOUSEKEEPING_TIME,
    CONF_LINKS,
    CONF_MANUFACTURER,
    CONF_MEDIA,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_MESSAGE,
    CONF_MOBILE_APP_ID,
    CONF_MOBILE_DEVICES,
    CONF_MOBILE_DISCOVERY,
    CONF_MODEL,
    CONF_OCCUPANCY,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_PHONE_NUMBER,
    CONF_PRIORITY,
    CONF_PTZ_CAMERA,
    CONF_PTZ_DELAY,
    CONF_PTZ_METHOD,
    CONF_PTZ_PRESET_DEFAULT,
    CONF_RECIPIENTS,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SCENARIOS,
    CONF_SELECTION,
    CONF_SELECTION_RANK,
    CONF_SIZE,
    CONF_TARGET_REQUIRED,
    CONF_TARGET_USAGE,
    CONF_TEMPLATE,
    CONF_TEMPLATE_PATH,
    CONF_TITLE,
    CONF_TITLE_TEMPLATE,
    CONF_TRANSPORT,
    CONF_TRANSPORTS,
    CONF_TTL,
    CONF_TUNE,
    CONF_URI,
    CONF_VOLUME,
    DELIVERY_SELECTION_VALUES,
    OCCUPANCY_ALL,
    OCCUPANCY_VALUES,
    OPTION_CHIME_ALIASES,
    OPTIONS_CHIME_DOMAINS,
    PRIORITY_VALUES,
    PTZ_METHOD_ONVIF,
    PTZ_METHOD_VALUES,
    RESERVED_DATA_KEYS,
    RESERVED_SCENARIO_NAMES,
    SELECTION_VALUES,
    TARGET_REQUIRE_ALWAYS,
    TARGET_REQUIRE_NEVER,
    TARGET_REQUIRE_OPTIONAL,
    TARGET_USE_FIXED,
    TARGET_USE_MERGE_ALWAYS,
    TARGET_USE_MERGE_ON_DELIVERY_TARGETS,
    TARGET_USE_ON_NO_ACTION_TARGETS,
    TARGET_USE_ON_NO_DELIVERY_TARGETS,
    TRANSPORT_VALUES,
)


class SelectionRank(StrEnum):
    FIRST = "FIRST"
    ANY = "ANY"
    LAST = "LAST"


type ConditionsFunc = Callable[[TemplateVarsType], bool]


def phone(value: str) -> str:
    """Validate a phone number"""
    regex = re.compile(r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")
    if not regex.match(value):
        raise vol.Invalid("Invalid Phone Number")
    return str(value)


def validate_scenario_names(scenarios: dict) -> dict:
    """Validate that scenario names are not reserved."""
    for name in scenarios:
        if name in RESERVED_SCENARIO_NAMES:
            raise vol.Invalid(f"'{name}' is a reserved scenario name")
    return scenarios


# TARGET_FIELDS includes entity, device, area, floor, label ids
TARGET_SCHEMA = vol.Any(  # order of schema matters, voluptuous forces into first it finds that works
    cv.TARGET_FIELDS
    | {
        vol.Optional(ATTR_EMAIL): vol.All(cv.ensure_list, [vol.Email]),
        vol.Optional(ATTR_PHONE): vol.All(cv.ensure_list, [phone]),
        vol.Optional(ATTR_MOBILE_APP_ID): vol.All(cv.ensure_list, [cv.service]),
        vol.Optional(ATTR_PERSON_ID): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(cv.string): vol.All(cv.ensure_list, [str]),
    },
    str,
    list[str],
)

DATA_SCHEMA = vol.Schema({vol.NotIn(RESERVED_DATA_KEYS): vol.Any(str, int, bool, float, dict, list)})

MOBILE_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_MANUFACTURER): cv.string,
    vol.Optional(CONF_MODEL): cv.string,
    vol.Optional(CONF_CLASS): cv.string,
    vol.Optional(CONF_MOBILE_APP_ID): cv.string,
    vol.Optional(CONF_DEVICE_TRACKER): cv.entity_id,
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
})
NOTIFICATION_DUPE_SCHEMA = vol.Schema({
    vol.Optional(CONF_TTL): cv.positive_int,
    vol.Optional(CONF_SIZE, default=100): cv.positive_int,
    vol.Optional(CONF_DUPE_POLICY, default=ATTR_DUPE_POLICY_MTSLP): vol.In([ATTR_DUPE_POLICY_MTSLP, ATTR_DUPE_POLICY_NONE]),
})


DELIVERY_CUSTOMIZE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_TARGET): TARGET_SCHEMA,
            vol.Optional(CONF_ENABLED): vol.Any(None, cv.boolean),
            vol.Optional(CONF_DATA): DATA_SCHEMA,
        },
    ),
)
LINK_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): cv.url,
    vol.Required(CONF_DESCRIPTION): cv.string,
    vol.Optional(CONF_ID): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_NAME): cv.string,
})


DELIVERY_CONFIG_SCHEMA = vol.Schema({  # shared by Transport Defaults and Delivery definitions
    # defaults set in model.DeliveryConfig
    vol.Optional(CONF_ACTION): cv.service,  # previously 'service:'
    vol.Optional(CONF_DEBUG): cv.boolean,
    vol.Optional(CONF_OPTIONS): dict,  # transport tuning
    vol.Optional(CONF_DATA): DATA_SCHEMA,
    vol.Optional(CONF_TARGET): TARGET_SCHEMA,
    vol.Optional(CONF_TARGET_REQUIRED): vol.Any(
        cv.boolean, vol.In([TARGET_REQUIRE_ALWAYS, TARGET_REQUIRE_NEVER, TARGET_REQUIRE_OPTIONAL])
    ),
    vol.Optional(CONF_TARGET_USAGE): vol.In([
        TARGET_USE_ON_NO_DELIVERY_TARGETS,
        TARGET_USE_ON_NO_ACTION_TARGETS,
        TARGET_USE_MERGE_ON_DELIVERY_TARGETS,
        TARGET_USE_MERGE_ALWAYS,
        TARGET_USE_FIXED,
    ]),
    vol.Optional(CONF_SELECTION): vol.All(cv.ensure_list, [vol.In(SELECTION_VALUES)]),
    vol.Optional(CONF_PRIORITY): vol.All(cv.ensure_list, [vol.Any(int, str, vol.In(list(PRIORITY_VALUES.keys())))]),
    vol.Optional(CONF_SELECTION_RANK): vol.In([
        SelectionRank.ANY,
        SelectionRank.FIRST,
        SelectionRank.LAST,
    ]),
})


DELIVERY_SCHEMA = vol.All(
    cv.deprecated(key=CONF_CONDITION),
    DELIVERY_CONFIG_SCHEMA.extend({
        vol.Required(CONF_TRANSPORT): vol.In(TRANSPORT_VALUES),
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_TEMPLATE): cv.string,
        vol.Optional(CONF_MESSAGE): vol.Any(None, cv.string),
        vol.Optional(CONF_TITLE): vol.Any(None, cv.string),
        vol.Optional(CONF_ENABLED): cv.boolean,
        vol.Optional(CONF_OCCUPANCY, default=OCCUPANCY_ALL): vol.In(OCCUPANCY_VALUES),
        vol.Optional(CONF_CONDITION): cv.CONDITIONS_SCHEMA,
        vol.Optional(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA,
    }),
)

TRANSPORT_SCHEMA = vol.All(
    cv.deprecated(key=CONF_DEVICE_DOMAIN),  # deprecated v1.9.0
    cv.deprecated(key=CONF_DEVICE_DISCOVERY),  # deprecated v1.9.0
    cv.deprecated(key=CONF_DEVICE_MODEL_INCLUDE),  # deprecated v1.9.0
    cv.deprecated(key=CONF_DEVICE_MODEL_EXCLUDE),  # deprecated v1.9.0
    vol.Schema({
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_DEVICE_DOMAIN): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DEVICE_MODEL_INCLUDE): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DEVICE_MODEL_EXCLUDE): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DEVICE_DISCOVERY): cv.boolean,
        vol.Optional(CONF_ENABLED, default=True): cv.boolean,
        vol.Optional(CONF_DELIVERY_DEFAULTS): DELIVERY_CONFIG_SCHEMA,
    }),
)
# Idea - differentiate enabled as recipient vs as occupant, for ALL_IN etc check
# May need condition, and also enabled if delivery disabled
# CONF_OCCUPANCY="occupancy"
# OPTION_OCCUPANCY_DEFAULT="default"
# OPTIONS_OCCUPANCY=[OPTION_OCCUPANCY_DEFAULT,OPTION_OCCUPANCY_EXCLUDE]
# OPTION_OCCUPANCY_EXCLUDE="exclude"


RECIPIENT_SCHEMA = vol.Schema({
    vol.Required(CONF_PERSON): cv.entity_id,
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_EMAIL): cv.string,
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
    # vol.Optional(CONF_OCCUPANCY,default=OPTION_OCCUPANCY_DEFAULT):vol.In(OPTIONS_OCCUPANCY),
    vol.Optional(CONF_TARGET): TARGET_SCHEMA,
    vol.Optional(CONF_PHONE_NUMBER): cv.string,
    vol.Optional(CONF_MOBILE_DISCOVERY, default=True): cv.boolean,
    vol.Optional(CONF_MOBILE_DEVICES, default=list): vol.All(cv.ensure_list, [MOBILE_DEVICE_SCHEMA]),
    vol.Optional(CONF_DELIVERY, default=dict): {cv.string: DELIVERY_CUSTOMIZE_SCHEMA},
})
CAMERA_SCHEMA = vol.Schema({
    vol.Required(CONF_CAMERA): cv.entity_id,
    vol.Optional(CONF_ALT_CAMERA): vol.All(cv.ensure_list, [cv.entity_id]),
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_URL): cv.url,
    vol.Optional(CONF_DEVICE_TRACKER): cv.entity_id,
    vol.Optional(CONF_PTZ_CAMERA): cv.entity_id,
    vol.Optional(CONF_PTZ_PRESET_DEFAULT, default=1): vol.Any(cv.positive_int, cv.string),
    vol.Optional(CONF_PTZ_DELAY, default=0): int,
    vol.Optional(CONF_PTZ_METHOD, default=PTZ_METHOD_ONVIF): vol.In(PTZ_METHOD_VALUES),
})
MEDIA_SCHEMA = vol.Schema({
    vol.Optional(ATTR_MEDIA_CAMERA_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_MEDIA_CAMERA_DELAY, default=0): int,
    vol.Optional(ATTR_MEDIA_CAMERA_PTZ_PRESET): vol.Any(cv.positive_int, cv.string),
    # URL fragments allowed
    vol.Optional(ATTR_MEDIA_CLIP_URL): vol.Any(cv.url, cv.string),
    vol.Optional(ATTR_MEDIA_SNAPSHOT_URL): vol.Any(cv.url, cv.string),
    vol.Optional(ATTR_JPEG_OPTS): dict,
    vol.Optional(ATTR_PNG_OPTS): dict,
})


SCENARIO_SCHEMA = vol.All(
    cv.deprecated(key=CONF_CONDITION),
    cv.deprecated(key="delivery_selection"),
    vol.Schema({
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_ENABLED, default=True): cv.boolean,
        vol.Optional(CONF_CONDITION): cv.CONDITIONS_SCHEMA,
        vol.Optional(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA,
        vol.Optional(CONF_MEDIA): MEDIA_SCHEMA,
        vol.Optional(CONF_ACTION_GROUP_NAMES, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("delivery_selection"): cv.string,
        vol.Optional(CONF_DELIVERY, default=dict): {cv.string: vol.Any(None, DELIVERY_CUSTOMIZE_SCHEMA)},
    }),
)
MOBILE_ACTION_CALL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ACTION): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_ACTION_CATEGORY): cv.string,
        vol.Optional(ATTR_ACTION_URL): cv.url,
        vol.Optional(ATTR_ACTION_URL_TITLE): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)
MOBILE_ACTION_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_ACTION, CONF_ACTION_TEMPLATE): cv.string,
        vol.Exclusive(CONF_TITLE, CONF_TITLE_TEMPLATE): cv.string,
        vol.Optional(CONF_URI): cv.url,
        vol.Optional(CONF_ICON): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


ARCHIVE_SCHEMA = vol.Schema({
    vol.Optional(CONF_ARCHIVE_PATH): cv.path,
    vol.Optional(CONF_ENABLED, default=False): cv.boolean,
    vol.Optional(CONF_ARCHIVE_DAYS, default=3): cv.positive_int,
    vol.Optional(CONF_ARCHIVE_MQTT_TOPIC): cv.string,
    vol.Optional(CONF_ARCHIVE_MQTT_QOS, default=0): cv.positive_int,
    vol.Optional(CONF_ARCHIVE_MQTT_RETAIN, default=True): cv.boolean,
    vol.Optional(CONF_ARCHIVE_PURGE_INTERVAL, default=60): cv.positive_int,
    vol.Optional(CONF_DEBUG, default=False): cv.boolean,
})

HOUSEKEEPING_SCHEMA = vol.Schema({
    vol.Optional(CONF_HOUSEKEEPING_TIME, default="00:00:01"): cv.time,
    vol.Optional(CONF_MEDIA_STORAGE_DAYS, default=7): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TEMPLATE_PATH, default=TEMPLATE_DIR): cv.path,
    vol.Optional(CONF_MEDIA_PATH, default=MEDIA_DIR): cv.path,
    vol.Optional(CONF_ARCHIVE, default={CONF_ENABLED: False}): ARCHIVE_SCHEMA,
    vol.Optional(CONF_HOUSEKEEPING, default={}): HOUSEKEEPING_SCHEMA,
    vol.Optional(CONF_DUPE_CHECK, default=dict): NOTIFICATION_DUPE_SCHEMA,
    vol.Optional(CONF_DELIVERY, default=dict): {cv.string: DELIVERY_SCHEMA},
    vol.Optional(CONF_ACTION_GROUPS, default=dict): {cv.string: [MOBILE_ACTION_SCHEMA]},
    vol.Optional(CONF_MOBILE_DISCOVERY, default=True): cv.boolean,
    vol.Optional(CONF_RECIPIENTS_DISCOVERY, default=True): cv.boolean,
    vol.Optional(CONF_RECIPIENTS, default=list): vol.All(cv.ensure_list, [RECIPIENT_SCHEMA]),
    vol.Optional(CONF_LINKS, default=list): vol.All(cv.ensure_list, [LINK_SCHEMA]),
    vol.Optional(CONF_SCENARIOS, default=dict): vol.All(
        {cv.string: SCENARIO_SCHEMA},
        validate_scenario_names,
    ),
    vol.Optional(CONF_TRANSPORTS, default=dict): {cv.string: TRANSPORT_SCHEMA},
    vol.Optional(CONF_CAMERAS, default=list): vol.All(cv.ensure_list, [CAMERA_SCHEMA]),
})
SUPERNOTIFY_SCHEMA = PLATFORM_SCHEMA

CHIME_ALIASES_SCHEMA = vol.Schema({
    vol.Required(OPTION_CHIME_ALIASES, default=dict): vol.Schema({
        cv.string: vol.Schema({
            cv.string: vol.Any(
                vol.Any(None, cv.string, vol.In(OPTIONS_CHIME_DOMAINS)),
                vol.Schema({
                    vol.Optional(CONF_ALIAS): cv.string,
                    vol.Optional(CONF_DOMAIN): cv.string,
                    vol.Optional(CONF_TUNE): cv.string,
                    vol.Optional(CONF_DATA): DATA_SCHEMA,
                    vol.Optional(CONF_VOLUME): float,
                    vol.Optional(CONF_TARGET): TARGET_SCHEMA,
                    vol.Optional(CONF_DURATION): cv.positive_int,
                }),
            )
        })
    })
})


ACTION_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DELIVERY): vol.Any(cv.string, [cv.string], {cv.string: vol.Any(None, DELIVERY_CUSTOMIZE_SCHEMA)}),
        vol.Optional(ATTR_PRIORITY): vol.Any(int, str, vol.In(list(PRIORITY_VALUES.keys()))),
        vol.Optional(ATTR_SCENARIOS_REQUIRE): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_SCENARIOS_APPLY): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_SCENARIOS_CONSTRAIN): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DELIVERY_SELECTION): vol.In(DELIVERY_SELECTION_VALUES),
        vol.Optional(ATTR_RECIPIENTS): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(ATTR_MEDIA): MEDIA_SCHEMA,
        vol.Optional(ATTR_MESSAGE_HTML): cv.string,
        vol.Optional(ATTR_ACTION_GROUPS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ACTIONS, default=[]): vol.All(cv.ensure_list, [MOBILE_ACTION_CALL_SCHEMA]),
        vol.Optional(ATTR_DEBUG, default=False): cv.boolean,
        vol.Optional(ATTR_DATA): vol.Any(None, DATA_SCHEMA),
        vol.Optional(ATTR_TIMESTAMP): cv.string,
    },
    extra=vol.ALLOW_EXTRA,  # allow other data, e.g. the android/ios mobile push
)

STRICT_ACTION_DATA_SCHEMA = ACTION_DATA_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA)
