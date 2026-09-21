from __future__ import annotations

import datetime as dt
import logging
import re
import time
import unicodedata
from abc import abstractmethod
from traceback import format_exception
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse

from homeassistant.components.notify.const import ATTR_TARGET
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
)
from homeassistant.exceptions import IntegrationError
from homeassistant.util import dt as dt_util

from custom_components.supernotify.model import (
    DebugTrace,
    EntityCategory,
    Target,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)

from .common import CallRecord
from .const import (
    ATTR_ENABLED,
    CONF_DELIVERY_DEFAULTS,
    INCLUSION_EXPLICIT,
)
from .model import DeliveryConfig, SuppressionReason
from .options import DeliveryOption

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

    from .context import Context
    from .delivery import Delivery, DeliveryRegistry
    from .hass_api import HomeAssistantAPI
    from .people import PeopleRegistry

# Markup that spoken transports hand straight to the voice assistant. Simplification
# strips angle brackets, so SSML has to be passed through untouched or the assistant
# ends up speaking the tag names out loud.
RE_MARKUP_TAG = re.compile(r"(</?[A-Za-z][\w.:-]*(?:\s[^<>]*?)?/?>)")
RE_MARKUP_TAG_NAME = re.compile(r"</?([A-Za-z][\w.:-]*)")
SSML_TAG_NAMES = frozenset({
    "alexa:name",
    "amazon:domain",
    "amazon:effect",
    "amazon:emotion",
    "audio",
    "break",
    "emphasis",
    "lang",
    "mark",
    "phoneme",
    "prosody",
    "say-as",
    "speak",
    "sub",
    "voice",
})

# Sign characters kept even though their Unicode category (Sm) would otherwise be stripped,
# so numeric values like "+3" or "-3" aren't left indistinguishable from "3".
SIGN_CHARS = frozenset("+-=%")

_LOGGER = logging.getLogger(__name__)


class Transport:
    """Base class for delivery transports.

    Sub classes integrste with Home Assistant notification services
    or alternative notification mechanisms.
    """

    name: str
    declared_options: ClassVar[list[DeliveryOption]] = []

    @abstractmethod
    def __init__(self, context: Context, transport_config: ConfigType | None = None) -> None:
        self.hass_api: HomeAssistantAPI = context.hass_api
        self.people_registry: PeopleRegistry = context.people_registry
        self.delivery_registry: DeliveryRegistry = context.delivery_registry
        self.context: Context = context
        transport_config = transport_config or {}
        self.transport_config = TransportConfig(transport_config, class_config=self.default_config)

        self.delivery_defaults: DeliveryConfig = self.transport_config.delivery_defaults
        self.config_enabled = self.transport_config.enabled
        self.enabled = self.config_enabled
        self.alias = self.transport_config.alias
        self.last_error_at: dt.datetime | None = None
        self.last_error_in: str | None = None
        self.last_error_message: str | None = None
        self.error_count: int = 0
        self._unavailable: bool = False

    async def initialize(self) -> None:
        """Async post-construction initialization"""
        if self.name is None:
            raise IntegrationError("Invalid nameless transport adaptor subclass")

    def setup_delivery_options(self, options: dict[str, Any], delivery_name: str) -> dict[str, Any]:
        return {}

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE

    @property
    def targets(self) -> Target:
        return self.delivery_defaults.target if self.delivery_defaults.target is not None else Target()

    @property
    def target_categories(self) -> list[str | EntityCategory]:
        """The target categories this transport understands, independent of any delivery.

        A plain string names a category directly (e.g. `ATTR_EMAIL`); an `EntityCategory`
        declares that the `entity_id` category is accepted, but only for entities matching
        its domain/platform constraints. Empty by default - a transport that doesn't declare
        anything here relies entirely on `Delivery.select_targets()`'s other qualification
        paths (its own name, its transport's name, or a delivery's own `OPTION_TARGET_CATEGORIES`
        override), which is the deliberate design for `generic`, a bring-your-own-categories
        transport. Queried via `Delivery.target_categories`, not directly - a `Transport`
        never needs to know about delivery-level config, only the reverse.
        """
        return []

    @property
    def default_config(self) -> TransportConfig:
        return TransportConfig()

    @property
    def inclusion_mode(self) -> list[str]:
        """The `inclusion` an auto-configured delivery for this transport should use.

        Explicit-only by default: most transports need a chat_id/channel/device_id the
        notification author must supply, have targets too opaque or ambiguous to map to
        a recipient/entity, or a channel too intrusive to fire on every notification.
        Override to return `[INCLUSION_DEFAULT]` for the few transports that can
        reasonably fire on every notification out of the box (e.g. email, mobile_push).

        Pulled out as a separate property so can be reported in the Transport Configuration
        section of the Developer documentation
        """
        return [INCLUSION_EXPLICIT]

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        """Whether this transport currently has what it needs to auto-configure a delivery.

        Default implementation just defers to `build_standard_deliveries()` and checks for
        a non-empty result - correct for any transport, but builds (and discards) the
        `DeliveryConfig`s to answer what's otherwise a yes/no question. Override with a
        standalone check (matching `build_standard_deliveries()`'s own condition) in a
        transport where that's cheap and doesn't require mutating `self.delivery_defaults`
        to find out - most transports that gate purely on hass_api state (a config entry, a
        registered service, discovered entities) can. Skip the override where viability can
        only be discovered by doing the same service/entity lookup
        `build_standard_deliveries()` itself needs to build the config (e.g. `discord`,
        `pushover`, `sms` - discovering *which* service is available - or `email`, which
        also decides *how* to send based on what's found).
        """
        return bool(self.build_standard_deliveries(hass_api))

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        """Build every 'standard' (auto-generatable) delivery this transport contributes,
        keyed by name: its own default (keyed by `self.name`) plus any extras.

        Only ever called once `is_viable()` has returned True for the same `hass_api` -
        callers must check that first. Most overrides trust this and skip re-checking
        their own viability condition; the exception is a transport whose viability can
        only be discovered by doing the very lookup this method needs anyway (see
        `is_viable()`'s docstring) - those keep their own guard and still return an empty
        dict, simply because there's nothing to gain by trusting the caller there.
        """
        return {}

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action == self.delivery_defaults.action

    def attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            ATTR_NAME: self.name,
            ATTR_ENABLED: self.enabled,
            CONF_DELIVERY_DEFAULTS: self.delivery_defaults,
        }
        if self.alias:
            attrs[ATTR_FRIENDLY_NAME] = self.alias
        if self.last_error_at:
            attrs["last_error_at"] = self.last_error_at
            attrs["last_error_in"] = self.last_error_in
            attrs["last_error_message"] = self.last_error_message
        attrs["error_count"] = self.error_count
        attrs.update(self.extra_attributes())
        return attrs

    def extra_attributes(self) -> dict[str, Any]:
        return {}

    @abstractmethod
    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # type: ignore # noqa: F821
        """Delivery implementation

        Args:
        ----
            envelope (Envelope): envelope to be delivered
            debug_trace (DebugTrace): debug info collector

        """

    def action_target(self, envelope: Envelope, entity_ids: list[str] | None = None) -> dict[str, Any]:  # type: ignore # noqa: F821
        """Build the target block of an action call from entity ids, plus any area/floor/label
        selectors the delivery passes through natively to the action"""
        target_data: dict[str, Any] = {}
        if entity_ids is not None:
            target_data[ATTR_ENTITY_ID] = entity_ids
        if envelope.delivery.passes_target_selectors and envelope.target is not None:
            target_data.update(envelope.target.selector_data())
        return target_data

    @staticmethod
    def has_action_target(target_data: dict[str, Any]) -> bool:
        return any(target_data.values())

    def set_action_data(self, action_data: dict[str, Any], key: str, data: Any | None) -> dict[str, Any]:  # ruff: ignore[any-type]
        if data is not None:
            action_data[key] = data
        return action_data

    async def call_action(
        self,
        envelope: Envelope,  # type: ignore # noqa: F821
        qualified_action: str | None = None,
        action_data: dict[str, Any] | None = None,
        target_data: dict[str, Any] | None = None,
        implied_target: bool = False,  # True if the qualified action implies a target
    ) -> bool:
        action_data = action_data or {}
        start_time = time.time()
        domain = service = None
        delivery: Delivery = envelope.delivery
        try:
            qualified_action = qualified_action or delivery.action
            if not qualified_action:
                _LOGGER.debug(
                    "SUPERNOTIFY Skipping %s action call with no service, targets %s",
                    envelope.delivery.name,
                    action_data.get(ATTR_TARGET),
                )
                envelope.skipped = 1
                envelope.skip_reason = SuppressionReason.NO_ACTION
                return False
            if (
                delivery.target_required == TargetRequired.ALWAYS
                and not action_data.get(ATTR_TARGET)
                and not action_data.get(ATTR_ENTITY_ID)
                and not implied_target
                and not target_data
            ):
                _LOGGER.debug(
                    "SUPERNOTIFY Skipping %s action call for service %s, missing targets",
                    envelope.delivery.name,
                    qualified_action,
                )
                envelope.skipped = 1
                envelope.skip_reason = SuppressionReason.NO_TARGET
                return False

            domain, service = qualified_action.split(".", 1)
            start_time = time.time()
            timestamp: dt.datetime | None = None
            if target_data:
                # home-assistant messes with the service_data passed by ref
                service_data_as_sent = dict(action_data)
                timestamp = dt.datetime.now(tz=dt_util.get_default_time_zone())
                service_response = await self.hass_api.call_service(
                    domain,
                    service,
                    service_data=action_data,
                    target=target_data,
                    debug=delivery.debug,
                    context=envelope.ha_context,
                )
                envelope.calls.append(
                    CallRecord(
                        timestamp,
                        time.time() - start_time,
                        domain,
                        service,
                        debug=delivery.debug,
                        action_data=service_data_as_sent,
                        target_data=target_data,
                        service_response=service_response,
                    )
                )
            else:
                service_data_as_sent = dict(action_data)
                timestamp = dt.datetime.now(tz=dt_util.get_default_time_zone())
                service_response = await self.hass_api.call_service(
                    domain, service, service_data=action_data, debug=delivery.debug, context=envelope.ha_context
                )
                envelope.calls.append(
                    CallRecord(
                        timestamp,
                        time.time() - start_time,
                        domain,
                        service,
                        debug=delivery.debug,
                        action_data=service_data_as_sent,
                        service_response=service_response,
                    )
                )

            envelope.delivered = 1
            self.log_delivery_recovered()
            return True
        except Exception as e:
            self.record_error(str(e), method="call_action")
            envelope.failed_calls.append(
                CallRecord(
                    timestamp,
                    time.time() - start_time,
                    domain,
                    service,
                    action_data,
                    target_data,
                    exception=str(e),
                )
            )
            self.log_delivery_failure(
                e, "SUPERNOTIFY Failed to notify %s via %s, data=%s", self.name, qualified_action, action_data
            )
            envelope.error_count += 1
            envelope.delivery_error = format_exception(e)
            return False

    def record_error(self, message: str, method: str) -> None:
        self.last_error_at = dt_util.utcnow()
        self.last_error_message = message
        self.last_error_in = method
        self.error_count += 1

    def log_delivery_failure(self, err: BaseException, message: str, *args: Any) -> None:
        """Log a delivery failure, passing the exception caught in the caller's except block.

        Logged at ERROR (with traceback) the first time this transport becomes unavailable,
        then downgraded to DEBUG for consecutive failures until it recovers - avoids
        spamming the log every notification while an external service/device stays down.
        Call alongside record_error(), which keeps tracking the lifetime error count
        regardless of log level.
        """
        if self._unavailable:
            _LOGGER.debug(message, *args, exc_info=err)
        else:
            _LOGGER.error(message, *args, exc_info=err)
            self._unavailable = True

    def log_delivery_recovered(self) -> None:
        """Call on a successful delivery - logs once if this transport was previously
        flagged unavailable, then clears the flag."""
        if self._unavailable:
            _LOGGER.info("SUPERNOTIFY %s transport recovered after prior delivery failures", self.name)
            self._unavailable = False

    def simplify(self, text: str | None, strip_urls: bool = False) -> str | None:
        """Simplify text for delivery transports with speaking or plain text interfaces.

        Spoken transports can be handed SSML, which the voice assistant parses itself.
        Simplification removes angle brackets, so applying it to SSML turns the markup
        into words the assistant reads out loud. When a spoken transport is given SSML,
        the tags are left alone and only the text around them is simplified, so emoji,
        URLs and symbols are still cleaned up.
        """
        if not text:
            return None
        if self.supported_features & TransportFeature.SPOKEN and self._is_ssml(text):
            simplified = "".join(
                fragment if index % 2 else self._simplify_around_markup(fragment, strip_urls)
                for index, fragment in enumerate(RE_MARKUP_TAG.split(text))
            )
        else:
            simplified = self._simplify_text(text, strip_urls)
        _LOGGER.debug("SUPERNOTIFY Simplified text to: %s", simplified)
        return simplified

    @staticmethod
    def _is_ssml(text: str) -> bool:
        """Tell SSML markup apart from stray angle brackets in ordinary text."""
        for tag in RE_MARKUP_TAG.findall(text):
            name = RE_MARKUP_TAG_NAME.match(tag)
            if name is not None and name.group(1).lower() in SSML_TAG_NAMES:
                return True
        return False

    @staticmethod
    def _simplify_text(text: str, strip_urls: bool = False) -> str:
        """Remove symbols, and optionally URLs, that can trip up voice assistants."""
        if strip_urls:
            words = text.split()
            text = " ".join(word for word in words if not (urlparse(word).scheme and urlparse(word).netloc))
        text = unicodedata.normalize("NFC", text)
        text = text.translate(str.maketrans("_", " ", "()£$<>"))
        return "".join(c for c in text if c in SIGN_CHARS or unicodedata.category(c) not in ("So", "Sk", "Sm", "Mn", "Sc"))

    @classmethod
    def _simplify_around_markup(cls, fragment: str, strip_urls: bool) -> str:
        """Simplify a fragment of text sitting between two SSML tags, keeping the
        whitespace at either end so that words do not end up glued to the markup."""
        if not fragment.strip():
            return fragment
        lead = fragment[: len(fragment) - len(fragment.lstrip())]
        trail = fragment[len(fragment.rstrip()) :]
        return f"{lead}{cls._simplify_text(fragment.strip(), strip_urls)}{trail}"
