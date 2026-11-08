"""Home Assistant's test helpers, from whichever package provides them for the Home Assistant
installed: pytest-home-assistant (`pytest_homeassistant`), published by Home Assistant itself from
2026.11, or pytest-homeassistant-custom-component before that. Remove once the oldest supported
Home Assistant has the first, importing from `pytest_homeassistant` directly.

Not the plugins module of either, which only conftest.py needs, and which can't be imported once
Home Assistant's recorder has been, as it has outside pytest, by the documentation build"""

try:
    from pytest_homeassistant.common import (  # type: ignore[import-not-found,unused-ignore]
        MockConfigEntry,
        async_fire_time_changed,
        async_mock_service,
        get_test_config_dir,
        mock_restore_cache,
        mock_restore_cache_with_extra_data,
    )
    from pytest_homeassistant.test_util.aiohttp import (  # type: ignore[import-not-found,unused-ignore]
        AiohttpClientMocker,
    )
    from pytest_homeassistant.typing import WebSocketGenerator  # type: ignore[import-not-found,unused-ignore]
except ImportError:
    from pytest_homeassistant_custom_component.common import (  # type: ignore[import-not-found,unused-ignore]
        MockConfigEntry,
        async_fire_time_changed,
        async_mock_service,
        get_test_config_dir,
        mock_restore_cache,
        mock_restore_cache_with_extra_data,
    )
    from pytest_homeassistant_custom_component.test_util.aiohttp import (  # type: ignore[import-untyped,unused-ignore]
        AiohttpClientMocker,
    )
    from pytest_homeassistant_custom_component.typing import (  # type: ignore[import-untyped,unused-ignore]
        WebSocketGenerator,
    )

__all__ = [
    "AiohttpClientMocker",
    "MockConfigEntry",
    "WebSocketGenerator",
    "async_fire_time_changed",
    "async_mock_service",
    "get_test_config_dir",
    "mock_restore_cache",
    "mock_restore_cache_with_extra_data",
]
