from custom_components.supernotify.notification import Notification

from .hass_setup_lib import TestingContext


async def test_alexa_whispering():
    """https://supernotify.rhizomatics.org.uk/recipes/alexa_whisper/"""
    ctx = TestingContext.from_config("""
  name: SuperNotifier
  platform: supernotify
  delivery:
    plain_email:
      transport: email
      action: notify.smtp
    alexa_inform:
      transport: alexa_devices
      target_definition: fixed
      target:
        entity_id:
          notify.kitchen_alexa_speak
    apple_push:
      transport: mobile_push
  scenarios:
    routine:
        alias: regular low level announcements
        condition:
          condition: and
          conditions:
            - "{{notification_priority in ['low']}}"

        delivery:
          plain_email:
          apple_push:
          alexa_inform:
            data:
              message_template: '<amazon:effect name="whispered">{{notification_message}}</amazon:effect>'
""")

    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", action_data={"priority": "low"}, target="joe@soapy.com")
    await uut.initialize()
    await uut.deliver()
    assert len(uut.delivered_envelopes) == 2
    index = {uut.delivered_envelopes[i].delivery_name: i for i in range(0, 2)}
    assert uut.delivered_envelopes[index["plain_email"]].calls[0].action_data["message"] == "testing 123"
    assert (
        uut.delivered_envelopes[index["alexa_inform"]].calls[0].action_data["message"]
        == '<amazon:effect name="whispered">testing 123</amazon:effect>'
    )


async def test_minimal_config_parses():
    ctx = TestingContext.from_config("""
    name: minimal
    platform: supernotify
    delivery:
      email:
        transport: email
        action: notify.smtp
""")
    await ctx.test_initialize()
    assert ctx.delivery("email") is not None
