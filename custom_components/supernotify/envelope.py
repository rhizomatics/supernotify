# mypy: disable-error-code="name-defined"

import copy
import logging
import time
import typing
from pathlib import Path
from typing import Any

from . import ATTR_TIMESTAMP, CONF_MESSAGE, CONF_TITLE, PRIORITY_MEDIUM
from .media_grab import grab_image
from .model import Target

if typing.TYPE_CHECKING:
    from custom_components.supernotify.common import CallRecord

    from .delivery import Delivery
    from .notification import Notification

_LOGGER = logging.getLogger(__name__)


class Envelope:
    """Wrap a notification with a specific set of targets and service data possibly customized for those targets"""

    def __init__(
        self,
        delivery: "Delivery",
        notification: "Notification | None" = None,
        target: Target | None = None,  # targets only for this delivery
        data: dict[str, Any] | None = None,  # notification data customized for this delivery
    ) -> None:
        self.target: Target = target or Target()
        self.delivery_name: str = delivery.name
        self.delivery: Delivery = delivery
        self._notification = notification
        self.notification_id = None
        self.media = None
        self.action_groups = None
        self.priority = PRIORITY_MEDIUM
        self.message: str | None = None
        self.title: str | None = None
        self.message_html: str | None = None
        self.data: dict[str, Any] = {}
        self.actions: list[dict[str, Any]] = []
        delivery_config_data: dict[str, Any] = {}
        if notification:
            self.notification_id = notification.id
            self.media = notification.media
            self.action_groups = notification.action_groups
            self.actions = notification.actions
            self.priority = notification.priority
            self.message = notification.message(delivery.name)
            self.message_html = notification.message_html
            self.title = notification.title(delivery.name)
            delivery_config_data = notification.delivery_data(delivery.name)

        if data:
            self.data = copy.deepcopy(delivery_config_data) if delivery_config_data else {}
            self.data |= data
        else:
            self.data = delivery_config_data if delivery_config_data else {}

        self.delivered: int = 0
        self.errored: int = 0
        self.skipped: int = 0
        self.calls: list[CallRecord] = []
        self.failed_calls: list[CallRecord] = []
        self.delivery_error: list[str] | None = None

    async def grab_image(self) -> Path | None:
        """Grab an image from a camera, snapshot URL, MQTT Image etc"""
        image_path: Path | None = None
        if self._notification:
            image_path = await grab_image(self._notification, self.delivery_name, self._notification.context)
        return image_path

    def core_action_data(self) -> dict[str, Any]:
        """Build the core set of `service_data` dict to pass to underlying notify service"""
        data: dict[str, Any] = {}
        # message is mandatory for notify platform
        data[CONF_MESSAGE] = self.message or ""
        timestamp = self.data.get(ATTR_TIMESTAMP)
        if timestamp:
            data[CONF_MESSAGE] = f"{data[CONF_MESSAGE]} [{time.strftime(timestamp, time.localtime())}]"
        if self.title:
            data[CONF_TITLE] = self.title
        return data

    def contents(self, minimal: bool = True) -> dict[str, typing.Any]:
        exclude_attrs = ["_notification"]
        if minimal:
            exclude_attrs.extend("resolved")
        json_ready = {k: v for k, v in self.__dict__.items() if k not in exclude_attrs}
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
