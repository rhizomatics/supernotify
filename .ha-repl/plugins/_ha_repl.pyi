# What ha-repl puts in a session before the plugins run, declared for linters
# and type checkers. Only `*.py` files are run as plugins, so this never is.
#
#     if TYPE_CHECKING:
#         from _ha_repl import MODE, hass, obj

from typing import Any, Literal

from homeassistant.core import HomeAssistant

MODE: Literal["live", "exec", "api"]
SERVER: str | None  # the configured server's name, None if connected by URL

# live and exec only - anything using it runs inside Home Assistant
hass: HomeAssistant

# every mode
obj: Any
sql: Any
hass_api: Any
