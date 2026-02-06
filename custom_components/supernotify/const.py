"""The Supernotify integration"""

from typing import Final

from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
)

CONF_ACTIONS: Final[str] = "actions"
CONF_TITLE: Final[str] = "title"
CONF_URI: Final[str] = "uri"
CONF_RECIPIENTS: Final[str] = "recipients"
CONF_RECIPIENTS_DISCOVERY: Final[str] = "recipients_discovery"
CONF_TEMPLATE_PATH: Final[str] = "template_path"
CONF_MEDIA_PATH: Final[str] = "media_path"
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
CONF_TRANSPORT: Final[str] = "transport"
CONF_TRANSPORTS: Final[str] = "transports"
CONF_DELIVERY: Final[str] = "delivery"
CONF_SELECTION: Final[str] = "selection"
CONF_SELECTION_RANK: Final[str] = "selection_rank"


CONF_DATA: Final[str] = "data"
CONF_OPTIONS: Final[str] = "options"
CONF_MOBILE: Final[str] = "mobile"
CONF_NOTIFY: Final[str] = "notify"

CONF_PRIORITY: Final[str] = "priority"
CONF_OCCUPANCY: Final[str] = "occupancy"
CONF_SCENARIOS: Final[str] = "scenarios"
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
CONF_PTZ_METHOD: Final[str] = "ptz_method"
CONF_PTZ_CAMERA: Final[str] = "ptz_camera"
CONF_PTZ_PRESET_DEFAULT: Final[str] = "ptz_default_preset"
CONF_ALT_CAMERA: Final[str] = "alt_camera"
CONF_CAMERAS: Final[str] = "cameras"
CONF_ARCHIVE_PURGE_INTERVAL: Final[str] = "purge_interval"
CONF_MEDIA_STORAGE_DAYS: Final[str] = "media_storage_days"

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
ATTR_MEDIA_SNAPSHOT_PATH = "snapshot_image_path"
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

OPTION_SIMPLIFY_TEXT = "simplify_text"
OPTION_STRIP_URLS = "strip_urls"
OPTION_MESSAGE_USAGE = "message_usage"
OPTION_RAW = "raw"
OPTION_JPEG = "jpeg_opts"
OPTION_PNG = "png_opts"
OPTION_TTS_ENTITY_ID = "tts_entity_id"
MEDIA_OPTION_REPROCESS = "reprocess"
OPTION_TARGET_CATEGORIES = "target_categories"
OPTION_UNIQUE_TARGETS = "unique_targets"
OPTION_TARGET_INCLUDE_RE = "target_include_re"  # deprecated v1.9.0
OPTION_TARGET_SELECT = "target_select"
OPTION_CHIME_ALIASES = "chime_aliases"
OPTION_DATA_KEYS_SELECT = "data_keys_select"
OPTION_DATA_KEYS_INCLUDE_RE = "data_keys_include_re"  # deprecated v1.9.0
OPTION_DATA_KEYS_EXCLUDE_RE = "data_keys_exclude_re"  # deprecated v1.9.0
OPTION_GENERIC_DOMAIN_STYLE = "handle_as_domain"
OPTION_STRICT_TEMPLATE = "strict_template"

SELECT_INCLUDE = "include"
SELECT_EXCLUDE = "exclude"

RE_DEVICE_ID = r"^[0-9a-f]{32}$"

RESERVED_DELIVERY_NAMES: list[str] = ["ALL"]
RESERVED_SCENARIO_NAMES: list[str] = ["NO_SCENARIO", "NULL"]
RESERVED_DATA_KEYS: list[str] = [ATTR_DOMAIN, ATTR_SERVICE, "action"]


CONF_DUPE_CHECK: Final[str] = "dupe_check"
CONF_DUPE_POLICY: Final[str] = "dupe_policy"
CONF_TTL: Final[str] = "ttl"
CONF_SIZE: Final[str] = "size"
ATTR_DUPE_POLICY_MTSLP: Final[str] = "dupe_policy_message_title_same_or_lower_priority"
ATTR_DUPE_POLICY_NONE: Final[str] = "dupe_policy_none"
CONF_MOBILE_APP_ID: Final[str] = "mobile_app_id"
CONF_TRANSPORT_DATA: Final[str] = "transport_data"


CONF_DEVICE_TRACKER: Final[str] = "device_tracker"


CONF_DEVICE_NAME: Final[str] = "device_name"
CONF_DEVICE_LABELS: Final[str] = "device_labels"

OPTION_DEVICE_DOMAIN: Final[str] = "device_domain"

OPTION_DEVICE_MODEL_SELECT: Final[str] = "device_model_select"
OPTION_DEVICE_MANUFACTURER_SELECT: Final[str] = "device_manufacturer_select"
OPTION_DEVICE_OS_SELECT: Final[str] = "device_os_select"
OPTION_DEVICE_LABEL_SELECT: Final[str] = "device_label_select"
OPTION_DEVICE_AREA_SELECT: Final[str] = "device_area_select"
OPTION_DEVICE_DISCOVERY: Final[str] = "device_discovery"


TARGET_REQUIRE_ALWAYS = "always"
TARGET_REQUIRE_NEVER = "never"
TARGET_REQUIRE_OPTIONAL = "optional"


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
]


CONF_DEVICE_DISCOVERY: Final[str] = "device_discovery"
CONF_DEVICE_DOMAIN: Final[str] = OPTION_DEVICE_DOMAIN
CONF_DEVICE_MODEL_INCLUDE: Final[str] = "device_model_include"
CONF_DEVICE_MODEL_EXCLUDE: Final[str] = "device_model_exclude"

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
