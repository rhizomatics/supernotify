import logging
import typing
from typing import Any

from homeassistant.const import (
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_DEFAULT,
    CONF_ENABLED,
    CONF_NAME,
    CONF_OPTIONS,
    CONF_TARGET,
)
from homeassistant.helpers import condition
from homeassistant.helpers.typing import ConfigType

from . import (
    CONF_DATA,
    CONF_MESSAGE,
    CONF_METHOD,
    CONF_OCCUPANCY,
    CONF_PRIORITY,
    CONF_SELECTION,
    CONF_TEMPLATE,
    CONF_TITLE,
    OCCUPANCY_ALL,
    RESERVED_DELIVERY_NAMES,
)
from .model import DeliveryConfig

if typing.TYPE_CHECKING:
    from .context import Context
    from .delivery_method import DeliveryMethod

_LOGGER = logging.getLogger(__name__)


class Delivery(DeliveryConfig):

    def __init__(self, name: str, conf: ConfigType, method: "DeliveryMethod") -> None:
        self.name: str = name
        self.alias: str | None = conf.get(CONF_ALIAS)
        self.method: DeliveryMethod = method
        method_defaults: DeliveryConfig = self.method.delivery_defaults
        super().__init__(conf, delivery_defaults=method_defaults)
        self.template: str | None = conf.get(CONF_TEMPLATE)
        self.default: bool = conf.get(CONF_DEFAULT, False)
        self.message: str | None = conf.get(CONF_MESSAGE)
        self.title: str | None = conf.get(CONF_TITLE)
        self.enabled: bool = conf.get(CONF_ENABLED, True)
        self.occupancy: str = conf.get(CONF_OCCUPANCY, OCCUPANCY_ALL)
        self.condition: ConfigType | None = conf.get(CONF_CONDITION)

    async def validate(self, context: "Context") -> bool:
        errors = 0
        if self.name in RESERVED_DELIVERY_NAMES:
            _LOGGER.warning("SUPERNOTIFY Delivery uses reserved word %s", self.name)
            await context.raise_issue(
                f"delivery_{self.name}_reserved_name",
                issue_key="delivery_reserved_name",
                issue_map={"delivery": self.name},
            )
            errors += 1
        if not self.method.validate_action(self.action):
            _LOGGER.warning("SUPERNOTIFY Invalid action definition for delivery %s (%s)", self.name, self.action)
            await context.raise_issue(
                f"delivery_{self.name}_invalid_action",
                issue_key="delivery_invalid_action",
                issue_map={"delivery": self.name, "action": self.action or ""},
            )
            errors += 1

        if self.condition and context.hass:
            try:
                await condition.async_validate_condition_config(context.hass, self.condition)
                passed = True
                exception = ""
            except Exception as e:
                passed = False
                exception = str(e)
            if not passed:
                _LOGGER.warning("SUPERNOTIFY Invalid delivery condition for %s: %s", self.name, self.condition)
                await context.raise_issue(
                    f"delivery_{self.name}_invalid_condition",
                    issue_key="delivery_invalid_condition",
                    issue_map={"delivery": self.name, "condition": str(self.condition), "exception": exception},
                )
                errors += 1
        return errors == 0

    def option(self, option_name: str) -> str | bool:
        """Get an option value from delivery config or method default options"""
        opt: str | bool | None = None
        if option_name in self.options:
            opt = self.options[option_name]
        if opt is None:
            _LOGGER.debug("SUPERNOTIFY No default in %s for option %s, setting to empty string", self.name, option_name)
            opt = ""
        return opt

    def option_bool(self, option_name: str) -> bool:
        return bool(self.option(option_name))

    def option_str(self, option_name: str) -> str:
        return str(self.option(option_name))

    def as_dict(self) -> dict[str, Any]:
        return {
            CONF_NAME: self.name,
            CONF_ALIAS: self.alias,
            CONF_METHOD: self.method.method,
            CONF_TEMPLATE: self.template,
            CONF_DEFAULT: self.default,
            CONF_MESSAGE: self.message,
            CONF_TITLE: self.title,
            CONF_ENABLED: self.enabled,
            CONF_OCCUPANCY: self.occupancy,
            CONF_CONDITION: self.condition,
            CONF_TARGET: self.target.as_dict() if self.target else None,
            CONF_ACTION: self.action,
            CONF_OPTIONS: self.options,
            CONF_DATA: self.data,
            CONF_SELECTION: self.selection,
            CONF_PRIORITY: self.priority,
        }
