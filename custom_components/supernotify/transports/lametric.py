"""LaMetric native transport for SuperNotify.

Sends messages and charts to LaMetric smart displays using the
HA lametric integration services (lametric.message, lametric.chart).

Requires: Home Assistant lametric integration (core, auto-discovered via mDNS/SSDP).
No action: required in delivery config — uses lametric.message or lametric.chart
based on presence of lametric_chart_data in envelope data.

Target: NEVER — LaMetric is a fixed device, not person-routed.
The device_id must be specified in delivery config data:

    deliveries:
      - name: lametric
        transport: lametric
        data:
          device_id: "49b6e2186ef37e164818aacb9cea1f53"

New data keys (all optional unless noted):
    device_id           str       REQUIRED. LaMetric device UUID from HA device registry.
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

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import TRANSPORT_LAMETRIC
from custom_components.supernotify.model import (
    DebugTrace,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.target_required = TargetRequired.NEVER
        return config

    def validate_action(self, action: str | None) -> bool:  # noqa: ARG002
        # No external action required - transport uses lametric.message / lametric.chart directly
        return True

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY lametric %s", envelope.message)

        # 1. Extract raw data (flat dict — rule #6)
        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # 2. Pop device_id (required — configured in delivery data)
        device_id: str | None = raw_data.pop("device_id", None)
        if not device_id:
            _LOGGER.debug(
                "SUPERNOTIFY lametric: device_id missing from delivery data, skipping. "
                "Add 'device_id: <uuid>' under data: in your lametric delivery config."
            )
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
        message = self.simplify(envelope.message, strip_urls=True) if lametric_simplify else envelope.message

        # 6A. CHART path — if lametric_chart_data is provided
        if lametric_chart_data is not None:
            if not isinstance(lametric_chart_data, list):
                _LOGGER.debug(
                    "SUPERNOTIFY lametric: lametric_chart_data must be a list of ints, got %s",
                    type(lametric_chart_data).__name__,
                )
                return False

            action_data: dict[str, Any] = {
                "device_id": device_id,
                "data": lametric_chart_data,  # field name is "data" for lametric.chart
                "cycles": final_cycles,
                "priority": final_priority,
                "icon_type": final_icon_type,
            }
            if final_sound:
                action_data["sound"] = final_sound

            return await self.call_action(
                envelope,
                qualified_action="lametric.chart",
                action_data=action_data,
            )

        # 6B. MESSAGE path (default)
        action_data = {
            "device_id": device_id,
            "message": message,
            "cycles": final_cycles,
            "priority": final_priority,
            "icon_type": final_icon_type,
        }
        if final_icon:
            action_data["icon"] = final_icon
        if final_sound:
            action_data["sound"] = final_sound

        return await self.call_action(
            envelope,
            qualified_action="lametric.message",
            action_data=action_data,
        )
