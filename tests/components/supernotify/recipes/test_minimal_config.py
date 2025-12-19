from tests.components.supernotify.hass_setup_lib import TestingContext


async def test_minimal_config_parses():
    ctx = TestingContext(
        yaml="""
    name: minimal
    platform: supernotify
    delivery:
      email:
        transport: email
        action: notify.smtp
"""
    )
    await ctx.test_initialize()
    assert ctx.delivery("email") is not None
