# Direct access to the running Supernotify from the ha-repl prompt.
#
#   engine                     the SupernotifyEngine behind the config entry
#   deliveries, scenarios,     its registries' contents, by name
#   people
#   last_notification, archive
#   switches, binary_sensors   Supernotify's entities, from `obj` (every mode)
#
# Nothing here is imported on your own machine. Supernotify runs inside Home
# Assistant, so the block that uses `hass` is sent there whole, imports and
# all, and its names are used from the prompt as if they were local.
#
# You will need to run `ha-repl trust` first before this plugin will be activated

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # For linters and type checkers only, and never run: what ha-repl itself
    # provides, declared in _ha_repl.pyi beside this file. They are used at
    # run time, which is the point, hence the noqa.
    from typing import Any

    from homeassistant_repl.plugin import MODE, hass, obj  # noqa: TC004

    from custom_components.supernotify import SupernotifyConfigEntry

if MODE != "api":
    from custom_components.supernotify.archive import NotificationArchive
    from custom_components.supernotify.delivery import Delivery, DeliveryRegistry
    from custom_components.supernotify.engine import SupernotifyEngine
    from custom_components.supernotify.notification import Notification
    from custom_components.supernotify.people import PeopleRegistry, Recipient
    from custom_components.supernotify.scenario import Scenario, ScenarioRegistry

    sn_yaml: dict[str, Any] = hass.data.get("supernotify", {})
    sn_ce: SupernotifyConfigEntry = hass.config_entries.async_entries("supernotify")[0]
    engine: SupernotifyEngine = sn_ce.runtime_data
    sn_dr: DeliveryRegistry = engine.context.delivery_registry
    sn_pr: PeopleRegistry = engine.context.people_registry
    sn_sr: ScenarioRegistry = engine.context.scenario_registry
    deliveries: dict[str, Delivery] = sn_dr.deliveries
    people: dict[str, Recipient] = sn_pr.people
    scenarios: dict[str, Scenario] = sn_sr.scenarios
    archive: NotificationArchive = engine.context.archive
    last_notification: Notification | None = engine.last_notification

switches = obj.find(platform="supernotify", domain="switch")
binary_sensors = obj.find(platform="supernotify", domain="binary_sensor")
