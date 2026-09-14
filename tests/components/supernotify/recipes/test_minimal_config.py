from tests.components.supernotify.hass_setup_lib import TestingContext


async def test_minimal_config_parses():
    # legacy config, test retained for bwd compat
    ctx = TestingContext(
        yaml="""
    name: minimal
    platform: supernotify
"""
    )
    await ctx.test_initialize()
    assert ctx.delivery("notify_entity") is not None
