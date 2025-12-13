"""The Supernotify integration"""

import logging
from collections.abc import Callable
from enum import StrEnum

import voluptuous as vol
from homeassistant.components.notify import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_DEBUG,
    CONF_DESCRIPTION,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_TARGET,
    CONF_URL,
    Platform,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import TemplateVarsType

_LOGGER = logging.getLogger(__name__)


class SelectionRank(StrEnum):
    FIRST = "FIRST"
    ANY = "ANY"
    LAST = "LAST"


type ConditionsFunc = Callable[[TemplateVarsType], bool]

DOMAIN = "supernotify"

PLATFORMS = [Platform.NOTIFY]
TEMPLATE_DIR = "/config/templates/supernotify"
MEDIA_DIR = "supernotify/media"


CONF_ACTIONS = "actions"
CONF_TITLE = "title"
CONF_URI = "uri"
CONF_RECIPIENTS = "recipients"
CONF_RECIPIENTS_DISCOVERY = "recipients_discovery"
CONF_TEMPLATE_PATH = "template_path"
CONF_MEDIA_PATH = "media_path"
CONF_HOUSEKEEPING = "housekeeping"
CONF_HOUSEKEEPING_TIME = "housekeeping_time"
CONF_ARCHIVE_PATH = "file_path"
CONF_ARCHIVE = "archive"
CONF_ARCHIVE_DAYS = "file_retention_days"
CONF_ARCHIVE_MQTT_TOPIC = "mqtt_topic"
CONF_ARCHIVE_MQTT_QOS = "mqtt_qos"
CONF_ARCHIVE_MQTT_RETAIN = "mqtt_retain"
CONF_TEMPLATE = "template"
CONF_DELIVERY_DEFAULTS = "delivery_defaults"
CONF_LINKS = "links"
CONF_PERSON = "person"
CONF_TRANSPORT = "transport"
CONF_TRANSPORTS = "transports"
CONF_DELIVERY = "delivery"
CONF_SELECTION = "selection"
CONF_SELECTION_RANK = "selection_rank"


CONF_DATA: str = "data"
CONF_OPTIONS: str = "options"
CONF_MOBILE: str = "mobile"
CONF_NOTIFY: str = "notify"
CONF_MOBILE_APP_ID: str = "mobile_app_id"
CONF_PHONE_NUMBER: str = "phone_number"
CONF_PRIORITY: str = "priority"
CONF_OCCUPANCY: str = "occupancy"
CONF_SCENARIOS: str = "scenarios"
CONF_MANUFACTURER: str = "manufacturer"
CONF_DEVICE_DISCOVERY: str = "device_discovery"
CONF_DEVICE_TRACKER: str = "device_tracker"
CONF_DEVICE_NAME: str = "device_name"
CONF_DEVICE_LABELS: str = "device_labels"
CONF_DEVICE_DOMAIN: str = "device_domain"
CONF_DEVICE_MODEL_INCLUDE: str = "device_model_include"
CONF_DEVICE_MODEL_EXCLUDE: str = "device_model_exclude"

CONF_MODEL: str = "model"
CONF_MESSAGE: str = "message"
CONF_TARGET_REQUIRED: str = "target_required"
CONF_MOBILE_DEVICES: str = "mobile_devices"
CONF_MOBILE_DISCOVERY: str = "mobile_discovery"
CONF_ACTION_TEMPLATE: str = "action_template"
CONF_ACTION_GROUPS: str = "action_groups"
CONF_TITLE_TEMPLATE: str = "title_template"
CONF_MEDIA: str = "media"
CONF_CAMERA: str = "camera"
CONF_CLIP_URL: str = "clip_url"
CONF_SNAPSHOT_URL: str = "snapshot_url"
CONF_PTZ_DELAY: str = "ptz_delay"
CONF_PTZ_METHOD: str = "ptz_method"
CONF_PTZ_PRESET_DEFAULT: str = "ptz_default_preset"
CONF_ALT_CAMERA: str = "alt_camera"
CONF_CAMERAS: str = "cameras"
CONF_ARCHIVE_PURGE_INTERVAL: str = "purge_interval"
CONF_MEDIA_STORAGE_DAYS = "media_storage_days"

OCCUPANCY_ANY_IN = "any_in"
OCCUPANCY_ANY_OUT = "any_out"
OCCUPANCY_ALL_IN = "all_in"
OCCUPANCY_ALL = "all"
OCCUPANCY_NONE = "none"
OCCUPANCY_ALL_OUT = "all_out"
OCCUPANCY_ONLY_IN = "only_in"
OCCUPANCY_ONLY_OUT = "only_out"

ATTR_ENABLED = "enabled"
ATTR_PRIORITY = "priority"
ATTR_ACTION = "action"
ATTR_SCENARIOS_REQUIRE = "require_scenarios"
ATTR_SCENARIOS_APPLY = "apply_scenarios"
ATTR_SCENARIOS_CONSTRAIN = "constrain_scenarios"
ATTR_DELIVERY = "delivery"
ATTR_DEFAULT = "default"
ATTR_NOTIFICATION_ID = "notification_id"
ATTR_DELIVERY_SELECTION = "delivery_selection"
ATTR_RECIPIENTS = "recipients"
ATTR_DATA = "data"
ATTR_MEDIA = "media"
ATTR_TITLE = "title"
ATTR_MEDIA_SNAPSHOT_URL = "snapshot_url"
ATTR_MEDIA_CAMERA_ENTITY_ID = "camera_entity_id"
ATTR_MEDIA_CAMERA_DELAY = "camera_delay"
ATTR_MEDIA_CAMERA_PTZ_PRESET = "camera_ptz_preset"
ATTR_MEDIA_CLIP_URL = "clip_url"
ATTR_ACTION_GROUPS = "action_groups"
CONF_ACTION_GROUP_NAMES = "action_groups"
ATTR_ACTION_CATEGORY = "action_category"
ATTR_ACTION_URL = "action_url"
ATTR_ACTION_URL_TITLE = "action_url_title"
ATTR_MESSAGE_HTML = "message_html"
ATTR_JPEG_OPTS = "jpeg_opts"
ATTR_PNG_OPTS = "png_opts"
ATTR_TIMESTAMP = "timestamp"
ATTR_DEBUG = "debug"
ATTR_ACTIONS = "actions"
ATTR_USER_ID = "user_id"
ATTR_PERSON_ID = "person_id"
ATTR_MOBILE_APP_ID = "mobile_app_id"
ATTR_EMAIL = "email"
ATTR_PHONE = "phone"
ATTR_ALIAS = "alias"

DELIVERY_SELECTION_IMPLICIT = "implicit"
DELIVERY_SELECTION_EXPLICIT = "explicit"
DELIVERY_SELECTION_FIXED = "fixed"

DELIVERY_SELECTION_VALUES = [DELIVERY_SELECTION_EXPLICIT, DELIVERY_SELECTION_FIXED, DELIVERY_SELECTION_IMPLICIT]
PTZ_METHOD_ONVIF = "onvif"
PTZ_METHOD_FRIGATE = "frigate"
PTZ_METHOD_VALUES = [PTZ_METHOD_ONVIF, PTZ_METHOD_FRIGATE]

SELECTION_FALLBACK_ON_ERROR = "fallback_on_error"
SELECTION_FALLBACK = "fallback"
SELECTION_BY_SCENARIO = "scenario"
SELECTION_DEFAULT = "default"
SELECTION_EXPLICIT = "explicit"
SELECTION_VALUES = [
    SELECTION_FALLBACK_ON_ERROR,
    SELECTION_EXPLICIT,
    SELECTION_BY_SCENARIO,
    SELECTION_DEFAULT,
    SELECTION_FALLBACK,
]

OCCUPANCY_VALUES = [
    OCCUPANCY_ALL_IN,
    OCCUPANCY_ALL_OUT,
    OCCUPANCY_ANY_IN,
    OCCUPANCY_ANY_OUT,
    OCCUPANCY_ONLY_IN,
    OCCUPANCY_ONLY_OUT,
    OCCUPANCY_ALL,
    OCCUPANCY_NONE,
]

PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"

PRIORITY_VALUES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_CRITICAL]

CONF_TARGET_USAGE = "target_usage"
TARGET_USE_ON_NO_DELIVERY_TARGETS = "no_delivery"
TARGET_USE_ON_NO_ACTION_TARGETS = "no_action"
TARGET_USE_FIXED = "fixed"
TARGET_USE_MERGE_ALWAYS = "merge_always"
TARGET_USE_MERGE_ON_DELIVERY_TARGETS = "merge_delivery"

OPTION_SIMPLIFY_TEXT = "simplify_text"
OPTION_STRIP_URLS = "strip_urls"
OPTION_MESSAGE_USAGE = "message_usage"
OPTION_JPEG = "jpeg_opts"
OPTION_PNG = "png_opts"
MEDIA_OPTION_REPROCESS = "reprocess"
OPTION_TARGET_CATEGORIES = "target_categories"
OPTION_UNIQUE_TARGETS = "unique_targets"
OPTION_TARGET_INCLUDE_RE = "target_include_re"
OPTION_CHIME_ALIASES = "chime_aliases"
OPTION_DATA_KEYS_INCLUDE_RE = "data_keys_include_re"
OPTION_DATA_KEYS_EXCLUDE_RE = "data_keys_exclude_re"

RE_DEVICE_ID = r"^[0-9a-f]{32}$"

RESERVED_DELIVERY_NAMES = ["ALL"]
RESERVED_SCENARIO_NAMES = ["NULL"]
RESERVED_DATA_KEYS = [ATTR_DOMAIN, ATTR_SERVICE, "action"]


CONF_DUPE_CHECK = "dupe_check"
CONF_DUPE_POLICY = "dupe_policy"
CONF_TTL = "ttl"
CONF_SIZE = "size"
ATTR_DUPE_POLICY_MTSLP = "dupe_policy_message_title_same_or_lower_priority"
ATTR_DUPE_POLICY_NONE = "dupe_policy_none"
# TARGET_FIELDS includes entity, device, area, floor, label ids
TARGET_SCHEMA = vol.Any(dict[str, list[str]], dict[str, str], str, list[str], cv.TARGET_FIELDS)

DATA_SCHEMA = vol.Schema({vol.NotIn(RESERVED_DATA_KEYS): vol.Any(str, int, bool, float, dict, list)})
MOBILE_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_MANUFACTURER): cv.string,
    vol.Optional(CONF_MODEL): cv.string,
    vol.Optional(CONF_MOBILE_APP_ID): cv.string,
    vol.Optional(CONF_DEVICE_TRACKER): cv.entity_id,
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
            vol.Optional(CONF_ENABLED, default=True): vol.Any(None, cv.boolean),
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

TARGET_REQUIRE_ALWAYS = "always"
TARGET_REQUIRE_NEVER = "never"
TARGET_REQUIRE_OPTIONAL = "optional"

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
    vol.Optional(CONF_PRIORITY): vol.All(cv.ensure_list, [vol.In(PRIORITY_VALUES)]),
    vol.Optional(CONF_SELECTION_RANK): vol.In([
        SelectionRank.ANY,
        SelectionRank.FIRST,
        SelectionRank.LAST,
    ]),
})

TRANSPORT_SMS = "sms"
TRANSPORT_MQTT = "mqtt"
TRANSPORT_EMAIL = "email"
TRANSPORT_ALEXA = "alexa_devices"
TRANSPORT_ALEXA_MEDIA_PLAYER = "alexa_media_player"
TRANSPORT_MOBILE_PUSH = "mobile_push"
TRANSPORT_MEDIA = "media"
TRANSPORT_CHIME = "chime"
TRANSPORT_GENERIC = "generic"
TRANSPORT_NOTIFY_ENTITY = "notify_entity"
TRANSPORT_PERSISTENT = "persistent"
TRANSPORT_VALUES = [
    TRANSPORT_SMS,
    TRANSPORT_MQTT,
    TRANSPORT_ALEXA,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_MOBILE_PUSH,
    TRANSPORT_CHIME,
    TRANSPORT_EMAIL,
    TRANSPORT_MEDIA,
    TRANSPORT_PERSISTENT,
    TRANSPORT_GENERIC,
    TRANSPORT_NOTIFY_ENTITY,
]

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
TRANSPORT_SCHEMA = vol.Schema({
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_DEVICE_DOMAIN): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEVICE_MODEL_INCLUDE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEVICE_MODEL_EXCLUDE): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEVICE_DISCOVERY, default=False): cv.boolean,
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_DELIVERY_DEFAULTS): DELIVERY_CONFIG_SCHEMA,
})
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
    vol.Optional(CONF_SCENARIOS, default=dict): {cv.string: SCENARIO_SCHEMA},
    vol.Optional(CONF_TRANSPORTS, default=dict): {cv.string: TRANSPORT_SCHEMA},
    vol.Optional(CONF_CAMERAS, default=list): vol.All(cv.ensure_list, [CAMERA_SCHEMA]),
})
SUPERNOTIFY_SCHEMA = PLATFORM_SCHEMA


CONF_TUNE = "tune"
CONF_VOLUME = "volume"
CONF_DURATION = "duration"

CHIME_ALIAS_SCHEMA = vol.Schema({
    vol.Optional(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_DEVICE_ID): cv.string,
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_TUNE): cv.string,
    vol.Optional(CONF_DATA): DATA_SCHEMA,
    vol.Optional(CONF_VOLUME): float,
    vol.Optional(CONF_DURATION): cv.positive_int,
})
CHIME_ALIAS_DOMAIN_SCHEMA = vol.Schema({vol.Required(cv.string, default=dict): {cv.string: CHIME_ALIAS_SCHEMA}})
CHIME_ALIASES_SCHEMA = vol.Schema({
    vol.Required(OPTION_CHIME_ALIASES, default=dict): vol.Schema({
        cv.string: vol.Schema({
            cv.string: vol.Any(
                cv.string,
                vol.Schema({
                    vol.Optional(CONF_ENTITY_ID): cv.entity_id,
                    vol.Optional(CONF_DEVICE_ID): cv.string,
                    vol.Optional(CONF_ALIAS): cv.string,
                    vol.Optional(CONF_TUNE): cv.string,
                    vol.Optional(CONF_DATA): DATA_SCHEMA,
                    vol.Optional(CONF_VOLUME): float,
                    vol.Optional(CONF_TARGET): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional(CONF_DURATION): cv.positive_int,
                }),
            )
        })
    })
})


ACTION_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DELIVERY): vol.Any(cv.string, [cv.string], {cv.string: vol.Any(None, DELIVERY_CUSTOMIZE_SCHEMA)}),
        vol.Optional(ATTR_PRIORITY): vol.In(PRIORITY_VALUES),
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
