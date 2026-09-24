"""The Supernotify integration"""

from typing import Final

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE,
    CONF_TARGET,
)

CONF_ACTIONS: Final[str] = "actions"  # not fully implemented
CONF_TITLE: Final[str] = "title"
CONF_URI: Final[str] = "uri"
CONF_RECIPIENTS: Final[str] = "recipients"
CONF_RECIPIENTS_DISCOVERY: Final[str] = "recipients_discovery"
CONF_TEMPLATE_PATH: Final[str] = "template_path"
CONF_MEDIA_PATH: Final[str] = "media_path"
CONF_MEDIA_URL_PREFIX: Final[str] = "media_url_prefix"
CONF_HOUSEKEEPING: Final[str] = "housekeeping"
CONF_HOUSEKEEPING_TIME: Final[str] = "housekeeping_time"
CONF_ARCHIVE_PATH: Final[str] = "file_path"
CONF_ARCHIVE: Final[str] = "archive"
CONF_ARCHIVE_DAYS: Final[str] = "file_retention_days"
CONF_ARCHIVE_MQTT_TOPIC: Final[str] = "mqtt_topic"
CONF_ARCHIVE_MQTT_QOS: Final[str] = "mqtt_qos"
CONF_ARCHIVE_MQTT_RETAIN: Final[str] = "mqtt_retain"
CONF_TEMPLATE: Final[str] = "template"
CONF_DELIVERY_DEFAULTS: Final[str] = "delivery_defaults"
CONF_LINKS: Final[str] = "links"
CONF_PERSON: Final[str] = "person"
CONF_USER_ID: Final[str] = "user_id"
CONF_TRANSPORT: Final[str] = "transport"
CONF_TRANSPORTS: Final[str] = "transports"
CONF_LOAD: Final[str] = "load"
CONF_DELIVERY: Final[str] = "delivery"
CONF_INCLUSION: Final[str] = "inclusion"
CONF_SELECTION: Final[str] = "selection"  # deprecated, use CONF_INCLUSION
CONF_SELECTION_RANK: Final[str] = "selection_rank"


CONF_DATA: Final[str] = "data"
CONF_OPTIONS: Final[str] = "options"
CONF_MOBILE: Final[str] = "mobile"
CONF_NOTIFY: Final[str] = "notify"

CONF_PRIORITY: Final[str] = "priority"
CONF_OCCUPANCY: Final[str] = "occupancy"
CONF_SCENARIOS: Final[str] = "scenarios"
CONF_SCENARIO_CONTROL: Final[str] = "scenario_control"
CONF_REFRESH_INTERVAL: Final[str] = "refresh_interval"
CONF_EXPOSE_STATE: Final[str] = "expose_state"
CONF_REFRESH: Final[str] = "refresh"
SCENARIO_STATE_REFRESH_DEFAULT: Final[int] = 60
CONF_MANUFACTURER: Final[str] = "manufacturer"
CONF_CLASS: Final[str] = "class"


CONF_MODEL: Final[str] = "model"
CONF_MESSAGE: Final[str] = "message"
CONF_TARGET_REQUIRED: Final[str] = "target_required"
CONF_MOBILE_DEVICES: Final[str] = "mobile_devices"
CONF_MOBILE_DISCOVERY: Final[str] = "mobile_discovery"
CONF_ACTION_TEMPLATE: Final[str] = "action_template"
CONF_ACTION_GROUPS: Final[str] = "action_groups"
CONF_TITLE_TEMPLATE: Final[str] = "title_template"
CONF_MEDIA: Final[str] = "media"
CONF_CAMERA: Final[str] = "camera"
CONF_CLIP_URL: Final[str] = "clip_url"
CONF_PTZ_DELAY: Final[str] = "ptz_delay"
CONF_SNAP_WAIT: Final[str] = "snap_wait"
CONF_PTZ_METHOD: Final[str] = "ptz_method"
CONF_PTZ_CAMERA: Final[str] = "ptz_camera"
CONF_PTZ_PRESET_DEFAULT: Final[str] = "ptz_default_preset"
CONF_ALT_CAMERA: Final[str] = "alt_camera"
CONF_CAMERAS: Final[str] = "cameras"
CONF_ARCHIVE_PURGE_INTERVAL: Final[str] = "purge_interval"
CONF_ARCHIVE_EVENT_NAME: Final[str] = "event_name"
CONF_ARCHIVE_EVENT_SELECTION: Final[str] = "event_selection"
CONF_ARCHIVE_DIAGNOSTICS: Final[str] = "diagnostics"
CONF_MEDIA_STORAGE_DAYS: Final[str] = "media_storage_days"

PLATFORM_FRIGATE = "frigate"

OCCUPANCY_ANY_IN = "any_in"
OCCUPANCY_ANY_OUT = "any_out"
OCCUPANCY_ALL_IN = "all_in"
OCCUPANCY_ALL = "all"
OCCUPANCY_NONE = "none"
OCCUPANCY_ALL_OUT = "all_out"
OCCUPANCY_ONLY_IN = "only_in"
OCCUPANCY_ONLY_OUT = "only_out"

ATTR_ENABLED = "enabled"
ATTR_TRANSPORT_ENABLED = "transport_enabled"
ATTR_PRIORITY = "priority"
ATTR_ACTION = "action"
ATTR_REPLY_TEXT = "reply_text"
ATTR_SCENARIOS_REQUIRE = "require_scenarios"
ATTR_SCENARIOS_APPLY = "apply_scenarios"
ATTR_FORCE_RESEND: Final[str] = "force_resend"
ATTR_SCENARIOS_CONSTRAIN = "constrain_scenarios"
ATTR_DELIVERY = "delivery"
ATTR_DEFAULT = "default"
ATTR_NOTIFICATION_ID = "notification_id"
ATTR_DELIVERY_SELECTION = "delivery_selection"
# supernotify.notify's free-form delivery field, merged into `delivery` with the delivery dropdown
ATTR_DELIVERY_CONTROL = "delivery_control"
ATTR_RECIPIENTS = "recipients"
ATTR_CUSTOM_TARGET = "custom_target"
ATTR_DATA = "data"
ATTR_EXTRA_DATA: Final[str] = "extra_data"
ATTR_MEDIA = "media"
ATTR_TITLE = "title"
ATTR_IMAGE = "image"
ATTR_VIDEO = "video"
ATTR_MEDIA_SNAPSHOT_URL = "snapshot_url"
ATTR_MEDIA_CAMERA_ENTITY_ID = "camera_entity_id"
ATTR_MEDIA_CAMERA_DELAY = "camera_delay"
ATTR_MEDIA_CAMERA_PTZ_PRESET = "camera_ptz_preset"
ATTR_MEDIA_CLIP_URL = "clip_url"
ATTR_MEDIA_SNAPSHOT_PATH = "snapshot_image_path"
ATTR_TOPIC = "topic"
ATTR_DISCORD_CHANNEL = "discord_channel"
ATTR_MATRIX_ROOM = "matrix_room"
ATTR_ACTION_GROUPS = "action_groups"
CONF_ACTION_GROUP_NAMES = "action_groups"
ATTR_ACTION_URL = "action_url"
ATTR_ACTION_URL_TITLE = "action_url_title"
ATTR_MESSAGE_HTML = "message_html"
ATTR_JPEG_OPTS = "jpeg_opts"
ATTR_PNG_OPTS = "png_opts"
ATTR_TIMESTAMP = "timestamp"
ATTR_SPOKEN_MESSAGE = "spoken_message"
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
PTZ_DELAY_DEFAULT = 10
SNAP_WAIT_DEFAULT = 15

INCLUSION_FALLBACK_ON_ERROR = "fallback_on_error"
INCLUSION_FALLBACK = "fallback"
INCLUSION_BY_SCENARIO = "scenario"
INCLUSION_DEFAULT = "default"
INCLUSION_EXPLICIT = "explicit"
INCLUSION_VALUES = [
    INCLUSION_FALLBACK_ON_ERROR,
    INCLUSION_EXPLICIT,
    INCLUSION_BY_SCENARIO,
    INCLUSION_DEFAULT,
    INCLUSION_FALLBACK,
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
PRIORITY_MINIMUM = "minimum"

PRIORITY_VALUES: dict[str, int] = {
    PRIORITY_MINIMUM: 1,
    PRIORITY_LOW: 2,
    PRIORITY_MEDIUM: 3,
    PRIORITY_HIGH: 4,
    PRIORITY_CRITICAL: 5,
}

CONF_TARGET_USAGE = "target_usage"
TARGET_USE_ON_NO_DELIVERY_TARGETS = "no_delivery"
TARGET_USE_ON_NO_ACTION_TARGETS = "no_action"
TARGET_USE_FIXED = "fixed"
TARGET_USE_MERGE_ALWAYS = "merge_always"
TARGET_USE_MERGE_ON_DELIVERY_TARGETS = "merge_delivery"

# Options constants have been moved to `options.py`

RE_DEVICE_ID = r"^[0-9a-f]{32}$"
RE_MEDIA_PLAYER_ENTITY_ID = r"^media_player\.[A-Za-z0-9_]+$"
RE_NOTIFY_ENTITY_ID = r"^notify\.[A-Za-z0-9_]+$"

RESERVED_DELIVERY_NAMES: list[str] = ["ALL"]
RESERVED_SCENARIO_NAMES: list[str] = ["NO_SCENARIO", "NULL"]
RESERVED_DATA_KEYS: list[str] = [ATTR_DOMAIN, ATTR_SERVICE, "action"]

CONF_DUPE_CHECK: Final[str] = "dupe_check"
CONF_DUPE_POLICY: Final[str] = "dupe_policy"
CONF_TTL: Final[str] = "ttl"
CONF_SIZE: Final[str] = "size"
ATTR_DUPE_POLICY_MTSLP: Final[str] = "dupe_policy_message_title_same_or_lower_priority"
ATTR_DUPE_POLICY_MT: Final[str] = "dupe_policy_message_title_same"
ATTR_DUPE_POLICY_NONE: Final[str] = "dupe_policy_none"
CONF_MOBILE_APP_ID: Final[str] = "mobile_app_id"
CONF_TRANSPORT_DATA: Final[str] = "transport_data"


CONF_DEVICE_TRACKER: Final[str] = "device_tracker"


CONF_DEVICE_NAME: Final[str] = "device_name"
CONF_DEVICE_LABELS: Final[str] = "device_labels"

MANUFACTURER_APPLE = "Apple"

TARGET_REQUIRE_ALWAYS = "always"
TARGET_REQUIRE_NEVER = "never"
TARGET_REQUIRE_OPTIONAL = "optional"

## Transports
# Defined here rather than transports.py so that the strings can be imported
# without the transports, and avoid circular references or heavier imports
TRANSPORT_SMS = "sms"
TRANSPORT_TTS = "tts"
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
TRANSPORT_NTFY = "ntfy"
TRANSPORT_GOTIFY = "gotify"
TRANSPORT_TELEGRAM = "telegram"
TRANSPORT_LAMETRIC = "lametric"
TRANSPORT_PUSHOVER = "pushover"
TRANSPORT_HTML5 = "html5"
TRANSPORT_MATRIX = "matrix"
TRANSPORT_KODI = "kodi"
TRANSPORT_DISCORD = "discord"
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
    TRANSPORT_TTS,
    TRANSPORT_GENERIC,
    TRANSPORT_NOTIFY_ENTITY,
    TRANSPORT_NTFY,
    TRANSPORT_GOTIFY,
    TRANSPORT_TELEGRAM,
    TRANSPORT_LAMETRIC,
    TRANSPORT_PUSHOVER,
    TRANSPORT_HTML5,
    TRANSPORT_MATRIX,
    TRANSPORT_KODI,
    TRANSPORT_DISCORD,
]

# The master list of target category names, independent of any one transport - both
# `Target` (for qualifying a target, e.g. `topic:my/topic` or `target: {topic: ...}`)
# and `Transport.target_categories` (for declaring which categories a transport accepts)
# reference this same list, rather than transports and targets each keeping their own.
TARGET_CATEGORY_VALUES = [
    ATTR_ENTITY_ID,
    ATTR_DEVICE_ID,
    ATTR_EMAIL,
    ATTR_PHONE,
    ATTR_MOBILE_APP_ID,
    ATTR_TOPIC,
    ATTR_DISCORD_CHANNEL,
    ATTR_MATRIX_ROOM,
]


CONF_CONNECTION: Final[str] = "connection"
CONF_ENCRYPTION: Final[str] = "encryption"

CONF_DEVICE_DISCOVERY: Final[str] = "device_discovery"
CONF_DEVICE_DOMAIN: Final[str] = "device_domain"
CONF_DEVICE_MODEL_INCLUDE: Final[str] = "device_model_include"
CONF_DEVICE_MODEL_EXCLUDE: Final[str] = "device_model_exclude"

# What a runtime override of a configured `enabled` flag can apply to - each also the unique_id
# prefix of the switch for it, e.g. switch unique_id "delivery_<name>"
OVERRIDE_KIND_SCENARIO: Final[str] = "scenario"
OVERRIDE_KIND_RECIPIENT: Final[str] = "recipient"
OVERRIDE_KIND_DELIVERY: Final[str] = "delivery"
OVERRIDE_KIND_TRANSPORT: Final[str] = "transport"
OVERRIDE_KINDS: Final[tuple[str, ...]] = (
    OVERRIDE_KIND_SCENARIO,
    OVERRIDE_KIND_RECIPIENT,
    OVERRIDE_KIND_DELIVERY,
    OVERRIDE_KIND_TRANSPORT,
)
# Entity state attributes too large, or changing too often, to be worth keeping in history
DELIVERY_UNRECORDED_ATTRIBUTES: Final[frozenset[str]] = frozenset({CONF_OPTIONS, CONF_DATA, CONF_TARGET})
TRANSPORT_UNRECORDED_ATTRIBUTES: Final[frozenset[str]] = frozenset({
    CONF_DELIVERY_DEFAULTS,
    "action_titles",
    "action_title_failures",
    "cached_templates",
})

CONF_SNOOZE = "snooze"
CONF_SNOOZE_TIME = "snooze_time"

# Config entry options for the LLM tools offered to Assist and MCP (beta), see llm.py
CONF_LLM_TOOLS: Final[str] = "llm_tools"
CONF_LLM_ACTION_TOOLS: Final[str] = "action_tools"
CONF_LLM_DIAGNOSTIC_TOOLS: Final[str] = "diagnostic_tools"
# sentences for Home Assistant's built-in conversation agent, which can't use LLM tools, see sentences.py
CONF_SENTENCE_COMMANDS: Final[str] = "sentence_commands"

# Idea - differentiate enabled as recipient vs as occupant, for ALL_IN etc check
# May need condition, and also enabled if delivery disabled
# CONF_OCCUPANCY="occupancy"
# OPTION_OCCUPANCY_DEFAULT="default"
# OPTIONS_OCCUPANCY=[OPTION_OCCUPANCY_DEFAULT,OPTION_OCCUPANCY_EXCLUDE]
# OPTION_OCCUPANCY_EXCLUDE="exclude"

CONF_PHONE_NUMBER: str = "phone_number"


CONF_TUNE: Final[str] = "tune"
CONF_VOLUME: Final[str] = "volume"
CONF_DURATION: Final[str] = "duration"

OPTIONS_CHIME_DOMAINS = ["media_player", "switch", "script", "rest_command", "siren", "alexa_devices"]
