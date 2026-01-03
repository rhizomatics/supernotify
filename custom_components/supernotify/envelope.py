import copy
import logging
import string
import time
import typing
import uuid
from typing import Any, cast

from anyio import Path
from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from jinja2 import TemplateError

from . import (
    ATTR_MEDIA,
    ATTR_MESSAGE_HTML,
    ATTR_PRIORITY,
    ATTR_TIMESTAMP,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    PRIORITY_MEDIUM,
)
from .common import DupeCheckable
from .context import Context
from .media_grab import grab_image
from .model import (
    ConditionVariables,
    DeliveryCustomization,
    MessageOnlyPolicy,
    SuppressionReason,
    Target,
    TargetRequired,
    TransportFeature,
)

if typing.TYPE_CHECKING:
    from custom_components.supernotify.common import CallRecord

    from .delivery import Delivery
    from .notification import Notification
    from .scenario import Scenario

_LOGGER = logging.getLogger(__name__)

HASH_PREP_TRANSLATION_TABLE = table = str.maketrans("", "", string.punctuation + string.digits)


class Envelope(DupeCheckable):
    """Wrap a notification with a specific set of targets and service data possibly customized for those targets"""

    def __init__(
        self,
        delivery: "Delivery",
        notification: "Notification | None" = None,
        target: Target | None = None,  # targets only for this delivery
        data: dict[str, Any] | None = None,
        context: Context | None = None,  # notification data customized for this delivery
    ) -> None:
        self.target: Target = target or Target()
        self.context: Context | None = context
        self.delivery_name: str = delivery.name
        self.delivery: Delivery = delivery
        self._notification = notification
        self.notification_id = None
        self.media = None
        self.action_groups = None
        self.priority = PRIORITY_MEDIUM
        self._message: str | None = None
        self._title: str | None = None
        self.message_html: str | None = None
        self.data: dict[str, Any] = {}
        self.actions: list[dict[str, Any]] = []
        if notification:
            delivery_config_data: dict[str, Any] = notification.delivery_data(delivery.name)
            self._enabled_scenarios: dict[str, Scenario] = notification.enabled_scenarios
            self._message = notification.message
            self._title = notification._title
            self.id = f"{notification.id}_{self.delivery_name}"
        else:
            delivery_config_data = {}
            self._enabled_scenarios = {}
            self.id = str(uuid.uuid1())
        if data:
            self.data = copy.deepcopy(delivery_config_data) if delivery_config_data else {}
            self.data |= data
        else:
            self.data = delivery_config_data if delivery_config_data else {}

        if notification:
            self.notification_id = notification.id
            self.media = notification.media
            self.action_groups = notification.action_groups
            self.actions = notification.actions
            self.priority = self.data.get(ATTR_PRIORITY, notification.priority)
            self.message_html = self.data.get(ATTR_MESSAGE_HTML, notification.message_html)
        if notification and hasattr(notification, "condition_variables"):  # yeuchh
            self.condition_variables = notification.condition_variables
        else:
            self.condition_variables = ConditionVariables()

        self.message = self._compute_message()
        self.title = self._compute_title()

        self.delivered: int = 0
        self.error_count: int = 0
        self.skipped: int = 0
        self.skip_reason: SuppressionReason | None = None
        self.calls: list[CallRecord] = []
        self.failed_calls: list[CallRecord] = []
        self.delivery_error: list[str] | None = None

    async def grab_image(self) -> Path | None:
        """Grab an image from a camera, snapshot URL, MQTT Image etc"""
        image_path: Path | None = None
        if self._notification:
            image_path = await grab_image(self._notification, self.delivery_name, self._notification.context)
        return image_path

    def core_action_data(self, force_message: bool = True) -> dict[str, Any]:
        """Build the core set of `service_data` dict to pass to underlying notify service"""
        # TODO: remove all logic, so only called to pre-populate `data`
        data: dict[str, Any] = {}
        # message is mandatory for notify platform
        if self.message is None:
            if force_message:
                data[ATTR_MESSAGE] = ""
        else:
            data[ATTR_MESSAGE] = self.message
        timestamp = self.data.get(ATTR_TIMESTAMP)
        if timestamp and ATTR_MESSAGE in data:
            data[ATTR_MESSAGE] = f"{data[ATTR_MESSAGE]} [{time.strftime(timestamp, time.localtime())}]"
        if self.title is not None:
            data[ATTR_TITLE] = self.title
        return data

    def contents(self, minimal: bool = True, **_kwargs: Any) -> dict[str, typing.Any]:
        exclude_attrs: list[str] = ["_notification", "context"]
        if minimal:
            exclude_attrs.append("delivery")
            features: TransportFeature = self.delivery.transport.supported_features
            if not features & TransportFeature.ACTIONS:
                exclude_attrs.extend(["actions", "action_groups"])
            if not features & TransportFeature.IMAGES and not features & TransportFeature.VIDEO:
                exclude_attrs.append(ATTR_MEDIA)
            if not features & TransportFeature.MESSAGE:
                exclude_attrs.extend(["message_html", "message"])
            if not features & TransportFeature.TITLE:
                exclude_attrs.append("title")
            if self.delivery.target_required == TargetRequired.NEVER:
                exclude_attrs.append("target")

        json_ready = {k: v for k, v in self.__dict__.items() if k not in exclude_attrs and not k.startswith("_")}
        json_ready["calls"] = [call.contents() for call in self.calls]
        json_ready["failedcalls"] = [call.contents() for call in self.failed_calls]
        return json_ready

    def __eq__(self, other: Any | None) -> bool:
        """Specialized equality check for subset of attributes"""
        if other is None or not isinstance(other, Envelope):
            return False
        return bool(
            self.target == other.target
            and self.delivery_name == other.delivery_name
            and self.data == other.data
            and self.notification_id == other.notification_id
        )

    def __repr__(self) -> str:
        """Return a concise string representation of the Envelope.

        The returned string includes the envelope's message, title, and delivery name
        in the form: Envelope(message=<message>,title=<title>,delivery=<delivery_name>).

        Primarily intended for debugging and logging; note that attribute values are
        inserted directly and may not be quoted or escaped.
        """
        return f"Envelope(message={self.message},title={self.title},delivery={self.delivery_name})"

    def _compute_title(self, ignore_usage: bool = False) -> str | None:
        # message and title reverse the usual defaulting, delivery config overrides runtime call

        title: str | None = None
        if self.delivery is None:
            title = self._title
        else:
            message_usage = self.delivery.option_str(OPTION_MESSAGE_USAGE)
            if not ignore_usage and message_usage.upper() in (MessageOnlyPolicy.USE_TITLE, MessageOnlyPolicy.COMBINE_TITLE):
                title = None
            else:
                title = self.delivery.title if self.delivery.title is not None else self._title
                if (
                    self.delivery.option_bool(OPTION_SIMPLIFY_TEXT) is True
                    or self.delivery.option_bool(OPTION_STRIP_URLS) is True
                ):
                    title = self.delivery.transport.simplify(title, strip_urls=self.delivery.option_bool(OPTION_STRIP_URLS))
        title = self._render_scenario_templates(title, "title_template", "notification_title")
        if title is None:
            return None
        return str(title)

    def _compute_message(self) -> str | None:
        # message and title reverse the usual defaulting, delivery config overrides runtime call

        msg: str | None = None
        if self.delivery is None:
            msg = self._message
        else:
            msg = self.delivery.message if self.delivery.message is not None else self._message
            message_usage: str = str(self.delivery.option_str(OPTION_MESSAGE_USAGE))
            if message_usage.upper() == MessageOnlyPolicy.USE_TITLE:
                title = self._compute_title(ignore_usage=True)
                if title:
                    msg = title
            elif message_usage.upper() == MessageOnlyPolicy.COMBINE_TITLE:
                title = self._compute_title(ignore_usage=True)
                if title:
                    msg = f"{title} {msg}"
            if self.delivery.option_bool(OPTION_SIMPLIFY_TEXT) is True or self.delivery.option_bool(OPTION_STRIP_URLS) is True:
                msg = self.delivery.transport.simplify(msg, strip_urls=self.delivery.option_bool(OPTION_STRIP_URLS))

        msg = self._render_scenario_templates(msg, "message_template", "notification_message")
        if msg is None:  # keep mypy happy
            return None
        return str(msg)

    def _render_scenario_templates(self, original: str | None, template_field: str, matching_ctx: str) -> str | None:
        """Apply templating to a field, like message or title"""
        rendered = original if original is not None else ""
        delivery_configs: list[DeliveryCustomization] = list(
            filter(None, (scenario.delivery_config(self.delivery.name) for scenario in self._enabled_scenarios.values()))
        )
        template_formats: list[str] = [
            dc.data_value(template_field)
            for dc in delivery_configs
            if dc is not None and dc.data_value(template_field) is not None
        ]
        if template_formats and self.context:
            if self.condition_variables:
                context_vars: dict[str, Any] = cast("dict[str,Any]", self.condition_variables.as_dict())
            else:
                context_vars = {}
            for template_format in template_formats:
                context_vars[matching_ctx] = rendered
                try:
                    template = self.context.hass_api.template(template_format)
                    rendered = template.async_render(variables=context_vars)
                except TemplateError as e:
                    self.error_count += 1
                    _LOGGER.warning(
                        "SUPERNOTIFY Rendering template %s for %s failed: %s", template_field, self.delivery.name, e
                    )
            return rendered
        return original

    # DupeCheckable implementation

    def hash(self) -> int:
        """Alpha hash to reduce noise from messages with timestamps or incrementing counts"""

        def alphaize(v: str | None) -> str | None:
            return v.translate(HASH_PREP_TRANSLATION_TABLE) if v else v

        return hash((alphaize(self._message), alphaize(self.delivery.name), self.target.hash_resolved(), alphaize(self._title)))
