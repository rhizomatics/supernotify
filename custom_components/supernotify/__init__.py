"""The SuperNotification integration"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import voluptuous as vol
from homeassistant.components.notify import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_DEFAULT,
    CONF_DESCRIPTION,
    CONF_EMAIL,
    CONF_ENABLED,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_TARGET,
    CONF_URL,
    STATE_HOME,
    STATE_NOT_HOME,
    Platform,
)
from homeassistant.helpers import config_validation as cv

from custom_components.supernotify.common import format_timestamp as format_timestamp

DOMAIN = "supernotify"

PLATFORMS = [Platform.NOTIFY]
TEMPLATE_DIR = "/config/templates/supernotify"
MEDIA_DIR = "supernotify/media"

CONF_ACTIONS = "actions"
CONF_TITLE = "title"
CONF_URI = "uri"
CONF_RECIPIENTS = "recipients"
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
CONF_LINKS = "links"
CONF_PERSON = "person"
CONF_METHOD = "method"
CONF_METHODS = "methods"
CONF_DELIVERY = "delivery"
CONF_SELECTION = "selection"

CONF_DATA: str = "data"
CONF_OPTIONS: str = "options"
CONF_MOBILE: str = "mobile"
CONF_NOTIFY: str = "notify"
CONF_NOTIFY_ACTION: str = "notify_action"
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
CONF_MODEL: str = "model"
CONF_MESSAGE: str = "message"
CONF_TARGETS_REQUIRED: str = "targets_required"
CONF_MOBILE_DEVICES: str = "mobile_devices"
CONF_MOBILE_DISCOVERY: str = "mobile_discovery"
CONF_ACTION_TEMPLATE: str = "action_template"
CONF_ACTION_GROUPS: str = "action_groups"
CONF_TITLE_TEMPLATE: str = "title_template"
CONF_DELIVERY_SELECTION: str = "delivery_selection"
CONF_MEDIA: str = "media"
CONF_CAMERA: str = "camera"
CONF_CLIP_URL: str = "clip_url"
CONF_SNAPSHOT_URL: str = "snapshot_url"
CONF_PTZ_DELAY: str = "ptz_delay"
CONF_PTZ_METHOD: str = "ptz_method"
CONF_PTZ_PRESET_DEFAULT: str = "ptz_default_preset"
CONF_ALT_CAMERA: str = "alt_camera"
CONF_CAMERAS: str = "cameras"
CONF_DEFAULT_ACTION: str = "default_action"

OCCUPANCY_ANY_IN = "any_in"
OCCUPANCY_ANY_OUT = "any_out"
OCCUPANCY_ALL_IN = "all_in"
OCCUPANCY_ALL = "all"
OCCUPANCY_NONE = "none"
OCCUPANCY_ALL_OUT = "all_out"
OCCUPANCY_ONLY_IN = "only_in"
OCCUPANCY_ONLY_OUT = "only_out"

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
ATTR_TIMESTAMP = "timestamp"
ATTR_DEBUG = "debug"
ATTR_ACTIONS = "actions"
ATTR_USER_ID = "user_id"

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
SELECTION_VALUES = [SELECTION_FALLBACK_ON_ERROR, SELECTION_BY_SCENARIO, SELECTION_DEFAULT, SELECTION_FALLBACK]

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
METHOD_SMS = "sms"
METHOD_EMAIL = "email"
METHOD_ALEXA = "alexa_devices"
METHOD_ALEXA_MEDIA_PLAYER = "alexa_media_player"
METHOD_MOBILE_PUSH = "mobile_push"
METHOD_MEDIA = "media"
METHOD_CHIME = "chime"
METHOD_GENERIC = "generic"
METHOD_PERSISTENT = "persistent"
METHOD_VALUES = [
    METHOD_SMS,
    METHOD_ALEXA,
    METHOD_ALEXA_MEDIA_PLAYER,
    METHOD_MOBILE_PUSH,
    METHOD_CHIME,
    METHOD_EMAIL,
    METHOD_MEDIA,
    METHOD_PERSISTENT,
    METHOD_GENERIC,
]

SCENARIO_DEFAULT = "DEFAULT"
SCENARIO_NULL = "NULL"
SCENARIO_TEMPLATE_ATTRS = ("message_template", "title_template")

RESERVED_DELIVERY_NAMES = ["ALL"]
RESERVED_SCENARIO_NAMES = [SCENARIO_DEFAULT, SCENARIO_NULL]
RESERVED_DATA_KEYS = [ATTR_DOMAIN, ATTR_SERVICE, "action"]

CONF_DUPE_CHECK = "dupe_check"
CONF_DUPE_POLICY = "dupe_policy"
CONF_TTL = "ttl"
CONF_SIZE = "size"
ATTR_DUPE_POLICY_MTSLP = "dupe_policy_message_title_same_or_lower_priority"
ATTR_DUPE_POLICY_NONE = "dupe_policy_none"

DATA_SCHEMA = vol.Schema({vol.NotIn(RESERVED_DATA_KEYS): vol.Any(str, int, bool, float, dict, list)})
MOBILE_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_MANUFACTURER): cv.string,
    vol.Optional(CONF_MODEL): cv.string,
    vol.Optional(CONF_NOTIFY_ACTION): cv.string,
    vol.Optional(CONF_DEVICE_TRACKER): cv.entity_id,
})
NOTIFICATION_DUPE_SCHEMA = vol.Schema({
    vol.Optional(CONF_TTL): cv.positive_int,
    vol.Optional(CONF_SIZE, default=100): cv.positive_int,
    vol.Optional(CONF_DUPE_POLICY, default=ATTR_DUPE_POLICY_MTSLP): vol.In([ATTR_DUPE_POLICY_MTSLP, ATTR_DUPE_POLICY_NONE]),
})
DELIVERY_CUSTOMIZE_SCHEMA = vol.Schema({
    vol.Optional(CONF_TARGET): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_DATA): DATA_SCHEMA,
})
LINK_SCHEMA = vol.Schema({
    vol.Optional(CONF_ID): cv.string,
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Required(CONF_DESCRIPTION): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})
DELIVERY_CONFIG_SCHEMA = vol.Schema({
    vol.Optional(CONF_TARGET): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_ACTION): cv.service,  # previously 'service:'
    vol.Optional(CONF_OPTIONS, default=dict): dict,
    vol.Optional(CONF_DATA): DATA_SCHEMA,
    vol.Optional(CONF_SELECTION, default=[SELECTION_DEFAULT]): vol.All(cv.ensure_list, [vol.In(SELECTION_VALUES)]),
    vol.Optional(CONF_PRIORITY, default=PRIORITY_VALUES): vol.All(cv.ensure_list, [vol.In(PRIORITY_VALUES)]),
})
METHOD_SCHEMA = vol.Schema({
    vol.Optional(CONF_TARGETS_REQUIRED): cv.boolean,
    vol.Optional(CONF_DEVICE_DOMAIN): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DEVICE_DISCOVERY): cv.boolean,
    vol.Optional(CONF_DEFAULT): DELIVERY_CONFIG_SCHEMA,
})
RECIPIENT_SCHEMA = vol.Schema({
    vol.Required(CONF_PERSON): cv.entity_id,
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_EMAIL): cv.string,
    vol.Optional(CONF_TARGET): vol.All(cv.ensure_list, [cv.string]),
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
})

DELIVERY_SCHEMA = DELIVERY_CONFIG_SCHEMA.extend({
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Required(CONF_METHOD): vol.In(METHOD_VALUES),
    vol.Optional(CONF_TEMPLATE): cv.string,
    vol.Optional(CONF_DEFAULT, default=False): cv.boolean,
    vol.Optional(CONF_MESSAGE): vol.Any(None, cv.string),
    vol.Optional(CONF_TITLE): vol.Any(None, cv.string),
    vol.Optional(CONF_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_OCCUPANCY, default=OCCUPANCY_ALL): vol.In(OCCUPANCY_VALUES),
    vol.Optional(CONF_CONDITION): cv.CONDITION_SCHEMA,
})

SCENARIO_SCHEMA = vol.Schema({
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_CONDITION): cv.CONDITION_SCHEMA,
    vol.Optional(CONF_MEDIA): MEDIA_SCHEMA,
    vol.Optional(CONF_ACTION_GROUP_NAMES, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_DELIVERY_SELECTION, default=DELIVERY_SELECTION_IMPLICIT): vol.In([
        DELIVERY_SELECTION_IMPLICIT,
        DELIVERY_SELECTION_EXPLICIT,
    ]),
    vol.Optional(CONF_DELIVERY, default=dict): {cv.string: vol.Any(None, DELIVERY_CUSTOMIZE_SCHEMA)},
})
ACTION_CALL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ACTION): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_ACTION_CATEGORY): cv.string,
        vol.Optional(ATTR_ACTION_URL): cv.url,
        vol.Optional(ATTR_ACTION_URL_TITLE): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)
ACTION_SCHEMA = vol.Schema(
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
})

HOUSEKEEPING_SCHEMA = vol.Schema({
    vol.Optional(CONF_HOUSEKEEPING_TIME, default="00:00:01"): cv.time,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TEMPLATE_PATH, default=TEMPLATE_DIR): cv.path,
    vol.Optional(CONF_MEDIA_PATH, default=MEDIA_DIR): cv.path,
    vol.Optional(CONF_ARCHIVE, default={CONF_ENABLED: False}): ARCHIVE_SCHEMA,
    vol.Optional(CONF_HOUSEKEEPING, default={}): HOUSEKEEPING_SCHEMA,
    vol.Optional(CONF_DUPE_CHECK, default=dict): NOTIFICATION_DUPE_SCHEMA,
    vol.Optional(CONF_DELIVERY, default=dict): {cv.string: DELIVERY_SCHEMA},
    vol.Optional(CONF_ACTION_GROUPS, default=dict): {cv.string: [ACTION_SCHEMA]},
    vol.Optional(CONF_RECIPIENTS, default=list): vol.All(cv.ensure_list, [RECIPIENT_SCHEMA]),
    vol.Optional(CONF_LINKS, default=list): vol.All(cv.ensure_list, [LINK_SCHEMA]),
    vol.Optional(CONF_SCENARIOS, default=dict): {cv.string: SCENARIO_SCHEMA},
    vol.Optional(CONF_METHODS, default=dict): {cv.string: METHOD_SCHEMA},
    vol.Optional(CONF_CAMERAS, default=list): vol.All(cv.ensure_list, [CAMERA_SCHEMA]),
})
SUPERNOTIFY_SCHEMA = PLATFORM_SCHEMA

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
        vol.Optional(ATTR_ACTIONS, default=[]): vol.All(cv.ensure_list, [ACTION_CALL_SCHEMA]),
        vol.Optional(ATTR_DEBUG, default=False): cv.boolean,
        vol.Optional(ATTR_DATA): vol.Any(None, DATA_SCHEMA),
    },
    extra=vol.ALLOW_EXTRA,  # allow other data, e.g. the android/ios mobile push
)

STRICT_ACTION_DATA_SCHEMA = ACTION_DATA_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA)


class TargetType(StrEnum):
    pass


class GlobalTargetType(TargetType):
    NONCRITICAL = "NONCRITICAL"
    EVERYTHING = "EVERYTHING"


class RecipientType(StrEnum):
    USER = "USER"
    EVERYONE = "EVERYONE"


class QualifiedTargetType(TargetType):
    METHOD = "METHOD"
    DELIVERY = "DELIVERY"
    CAMERA = "CAMERA"
    PRIORITY = "PRIORITY"
    ACTION = "ACTION"


class CommandType(StrEnum):
    SNOOZE = "SNOOZE"
    SILENCE = "SILENCE"
    NORMAL = "NORMAL"


class MessageOnlyPolicy(StrEnum):
    STANDARD = "STANDARD"  # independent title and message
    USE_TITLE = "USE_TITLE"  # use title in place of message, no title
    COMBINE_TITLE = "COMBINE_TITLE"  # use combined title and message as message, no title


@dataclass
class ConditionVariables:
    """Variables presented to all condition evaluations

    Attributes
    ----------
        applied_scenarios (list[str]): Scenarios that have been applied
        required_scenarios (list[str]): Scenarios that must be applied
        constrain_scenarios (list[str]): Only scenarios in this list, or in explicit apply_scenarios, can be applied
        notification_priority (str): Priority of the notification
        notification_message (str): Message of the notification
        notification_title (str): Title of the notification
        occupancy (list[str]): List of occupancy scenarios

    """

    applied_scenarios: list[str] = field(default_factory=list)
    required_scenarios: list[str] = field(default_factory=list)
    constrain_scenarios: list[str] = field(default_factory=list)
    notification_priority: str = PRIORITY_MEDIUM
    notification_message: str = ""
    notification_title: str = ""
    occupancy: list[str] = field(default_factory=list)

    def __init__(
        self,
        applied_scenarios: list[str] | None = None,
        required_scenarios: list[str] | None = None,
        constrain_scenarios: list[str] | None = None,
        delivery_priority: str | None = PRIORITY_MEDIUM,
        occupiers: dict[str, list[dict[str, Any]]] | None = None,
        message: str | None = None,
        title: str | None = None,
    ) -> None:
        occupiers = occupiers or {}
        self.occupancy = []
        if not occupiers.get(STATE_NOT_HOME) and occupiers.get(STATE_HOME):
            self.occupancy.append("ALL_HOME")
        elif occupiers.get(STATE_NOT_HOME) and not occupiers.get(STATE_HOME):
            self.occupancy.append("ALL_AWAY")
        if len(occupiers.get(STATE_HOME, [])) == 1:
            self.occupancy.extend(["LONE_HOME", "SOME_HOME"])
        elif len(occupiers.get(STATE_HOME, [])) > 1 and occupiers.get(STATE_NOT_HOME):
            self.occupancy.extend(["MULTI_HOME", "SOME_HOME"])
        self.applied_scenarios = applied_scenarios or []
        self.required_scenarios = required_scenarios or []
        self.constrain_scenarios = constrain_scenarios or []
        self.notification_priority = delivery_priority or PRIORITY_MEDIUM
        self.notification_message = message or ""
        self.notification_title = title or ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "applied_scenarios": self.applied_scenarios,
            "required_scenarios": self.required_scenarios,
            "constrain_scenarios": self.constrain_scenarios,
            "notification_message": self.notification_message,
            "notification_title": self.notification_title,
            "occupancy": self.occupancy,
        }
