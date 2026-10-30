"""LaMetric native transport for SuperNotify.

Sends messages and charts to LaMetric smart displays using the
HA lametric integration services (lametric.message, lametric.chart).

Requires: Home Assistant lametric integration (core, auto-discovered via mDNS/SSDP).
No action: required in delivery config — uses lametric.message or lametric.chart
based on presence of lametric_chart_data in envelope data.

Targets are the `notify` entity the integration creates for each device, whose device is
looked up, or a fixed device_id in the delivery config data:

    delivery:
      lametric:
        transport: lametric
        data:
          device_id: "49b6e2186ef37e164818aacb9cea1f53"

There's no room for a title on the display, so only the message is shown.

New data keys (all optional unless noted):
    device_id           str       LaMetric device UUID from HA device registry, used when
                                  no LaMetric notify entity is targeted.
                                  Obtain from: HA Settings → Devices → LaMetric → device ID.
                                  Example: "49b6e2186ef37e164818aacb9cea1f53"
    lametric_sound      str       Built-in sound name. Overrides priority default.
                                  Built-in sounds: alarm1, alarm2, ..., alarm13,
                                  bicycle, car, cash, cat, dog, dog2, energy,
                                  knock-knock, letter_email, lose1, lose2,
                                  negative1, negative2, negative3, negative4, negative5,
                                  notification, notification2, notification3, notification4,
                                  open_door, positive1, ..., positive6,
                                  statistic, thunder, water1, water2,
                                  win, win2, wind, wind_short.
                                  Omit or set None for silent notification.
    lametric_icon       str       Icon ID override (e.g. "i2867", "a1784").
                                  Overrides priority-based default icon.
                                  Full icon list: https://developer.lametric.com/icons
    lametric_cycles     int       Display cycles override.
                                  0 = permanent (stays until dismissed manually).
                                  1+ = number of scroll cycles, then auto-dismiss.
                                  Overrides priority default.
    lametric_icon_type  str       Icon style: "none", "info", "alert".
                                  "alert" produces a red flashing icon.
                                  Overrides priority default.
    lametric_chart_data list[int] If present, sends lametric.chart instead of lametric.message.
                                  List of integers representing bar chart values.
                                  Example: [10, 30, 50, 80, 60, 20]
    lametric_simplify   bool      If True, apply simplify() to message text
                                  (strips URLs, shortens for small physical display).
                                  Default: False.

Priority defaults (auto-applied when keys not specified):
    critical → priority=critical, cycles=0 (permanent), icon_type=alert, sound=alarm1,    icon=a1784
    high     → priority=warning,  cycles=2,             icon_type=alert, sound=knock-knock, icon=i140
    medium   → priority=info,     cycles=1,             icon_type=info,  sound=notification, icon=i2867
    low      → priority=info,     cycles=1,             icon_type=none,  sound=None (silent), icon=i2867
    minimum  → priority=info,     cycles=1,             icon_type=none,  sound=None (silent), icon=None
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import TRANSPORT_LAMETRIC
from custom_components.supernotify.model import (
    DebugTrace,
    SuppressionReason,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.target import TargetEntityCategory
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)

HA_LAMETRIC_DOMAIN = "lametric"

# Priority mapping: SuperNotify string → LaMetric priority string
_PRIORITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "warning",
    "medium": "info",
    "low": "info",
    "minimum": "info",
}

# Default display cycles per priority (0 = permanent until dismissed)
_CYCLES_MAP: dict[str, int] = {
    "critical": 0,  # stays on display until manually dismissed
    "high": 2,
    "medium": 1,
    "low": 1,
    "minimum": 1,
}

# Icon type per priority ("alert" = red flashing, "info" = blue, "none" = no highlight)
_ICON_TYPE_MAP: dict[str, str] = {
    "critical": "alert",
    "high": "alert",
    "medium": "info",
    "low": "none",
    "minimum": "none",
}

# Default sound per priority (None = silent)
_SOUND_MAP: dict[str, str | None] = {
    "critical": "alarm1",
    "high": "knock-knock",
    "medium": "notification",
    "low": None,
    "minimum": None,
}

# Default icon ID per priority (None = no icon)
_ICON_MAP: dict[str, str | None] = {
    "critical": "a1784",  # animated alert icon (red)
    "high": "i140",  # exclamation mark
    "medium": "i2867",  # bell icon (already used by Lollo)
    "low": "i2867",  # bell icon
    "minimum": None,  # text only
}


class LaMetricTransport(Transport):
    """LaMetric smart display transport for SuperNotify.

    Delivers notifications to LaMetric TIME devices via the HA lametric
    integration. Supports text messages and bar charts with full priority
    mapping (sound, icon, cycles, icon_type auto-selected per priority level).
    """

    name = TRANSPORT_LAMETRIC
    integration_domain = HA_LAMETRIC_DOMAIN

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE

    @property
    def default_config(self) -> TransportConfig:
        config = super().default_config
        # a delivery may instead fix its display with device_id in data, with no target - like
        # mqtt's topic, Notification._target_required() stops the standard delivery firing unprompted
        config.delivery_defaults.target_required = TargetRequired.OPTIONAL
        return config

    @property
    def unique_target_categories(self) -> list[str | TargetEntityCategory]:
        # the notify entity for each display is the integration's own, claimed ahead of the
        # generic notify_entity transport, like ntfy's
        return [TargetEntityCategory(domain="notify", platform=HA_LAMETRIC_DOMAIN)]

    def device_ids(self, envelope: Envelope, device_id: str | None) -> list[str]:
        """The device of each targeted LaMetric notify entity, or else the fixed device_id, like mqtt's topic"""
        device_ids: list[str] = []
        for entity_id in envelope.target.domain_entity_ids("notify") if envelope.target else []:
            entity_device_id: str | None = self.hass_api.device_for_entity(entity_id)
            if entity_device_id is None:
                _LOGGER.warning("SUPERNOTIFY lametric: no device found for %s", entity_id)
            elif entity_device_id not in device_ids:
                device_ids.append(entity_device_id)
        if not device_ids and device_id:
            device_ids.append(device_id)
        return device_ids

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        return hass_api.find_config_entry_data(HA_LAMETRIC_DOMAIN) is not None

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        return {self.name: {}}

    def validate_action(self, action: str | None) -> bool:
        # No external action required - transport uses lametric.message / lametric.chart directly
        return True

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY lametric %s", envelope.message)

        # 1. Extract raw data (flat dict — rule #6)
        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # 2. Displays to send to, from device_id in data or LaMetric notify entity targets
        device_ids: list[str] = self.device_ids(envelope, raw_data.pop("device_id", None))
        if not device_ids:
            _LOGGER.warning("SUPERNOTIFY lametric: no LaMetric notify entity target or device_id in delivery data, skipping")
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.NO_TARGET
            return False

        # 3. Pop all lametric-specific keys (must NOT reach the HA service)
        lametric_sound = raw_data.pop("lametric_sound", None)
        lametric_icon = raw_data.pop("lametric_icon", None)
        lametric_cycles = raw_data.pop("lametric_cycles", None)
        lametric_icon_type = raw_data.pop("lametric_icon_type", None)
        lametric_chart_data = raw_data.pop("lametric_chart_data", None)
        lametric_simplify = boolify(raw_data.pop("lametric_simplify", False), default=False)

        # 4. Resolve priority → default values
        sn_priority = envelope.priority or "medium"
        final_priority = _PRIORITY_MAP.get(sn_priority, "info")
        final_cycles = lametric_cycles if lametric_cycles is not None else _CYCLES_MAP.get(sn_priority, 1)
        final_icon_type = lametric_icon_type if lametric_icon_type is not None else _ICON_TYPE_MAP.get(sn_priority, "none")
        final_sound = lametric_sound if lametric_sound is not None else _SOUND_MAP.get(sn_priority)
        final_icon = lametric_icon if lametric_icon is not None else _ICON_MAP.get(sn_priority)

        # 5. Optionally simplify message text for small physical display
        message = (self.simplify(envelope.message, strip_urls=True) if lametric_simplify else envelope.message) or ""

        # 6A. CHART path — if lametric_chart_data is provided
        if lametric_chart_data is not None:
            if not isinstance(lametric_chart_data, list):
                _LOGGER.warning(
                    "SUPERNOTIFY lametric: lametric_chart_data must be a list of ints, got %s",
                    type(lametric_chart_data).__name__,
                )
                return False

            qualified_action = "lametric.chart"
            action_data: dict[str, Any] = {
                "data": lametric_chart_data,  # field name is "data" for lametric.chart
                "cycles": final_cycles,
                "priority": final_priority,
                "icon_type": final_icon_type,
            }
        else:
            # 6B. MESSAGE path (default)
            qualified_action = "lametric.message"
            action_data = {
                "message": message,
                "cycles": final_cycles,
                "priority": final_priority,
                "icon_type": final_icon_type,
            }
            if final_icon:
                action_data["icon"] = final_icon
        if final_sound:
            action_data["sound"] = final_sound

        # the actions take a single device_id, so one call per display
        results: list[bool] = [
            await self.call_action(
                envelope,
                qualified_action=qualified_action,
                action_data={"device_id": device_id, **action_data},
                implied_target=True,
            )
            for device_id in device_ids
        ]
        return all(results)
