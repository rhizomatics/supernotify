
from urllib.parse import urlparse

from homeassistant.core import (
    HomeAssistant,
)
from pytest_httpserver import BlockingHTTPServer

from conftest import TestImage
from custom_components.supernotify.notification import Notification
from tests.components.supernotify.hass_setup_lib import TestingContext


async def test_frigate_blueprint_notification(hass: HomeAssistant, local_server: BlockingHTTPServer, sample_jpeg: TestImage):
    """Handling of a Frigate Blueprint generated push message"""
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
  name: Supernotify
  platform: supernotify
  delivery:
    plain_email:
      transport: email
      action: notify.smtp
      target: joe@mctest.org
    apple_push:
      transport: mobile_push
      target: mobile_app.iphone
""",
        services={"notify": ["smtp"], "mobile_app": ["iphone"]},
    )

    await ctx.test_initialize()

    uut = Notification(ctx, message="A Car was detected on the Driveway camera.", target=None,
    title=None, action_data={
      "tag": "1766218266.042615-blamq9",
      "group": "driveway-frigate-notification",
      "color": "#03a9f4",
      "subject": "",
      "image": "http://127.0.0.1/api/frigate/notifications/1766218266.042615-blamq9/thumbnail.jpg",
      "video": "https://home.43acaciaroad.org/api/frigate/notifications/1766218266.042615-blamq9/driveway/master.m3u8",
      "clickAction": "https://home.43acaciaroad.org/api/frigate/notifications/1766218266.042615-blamq9/driveway/clip.mp4",
      "ttl": 0,
      "priority": "high",
      "notification_icon": "mdi:homeassistant",
      "sticky": False,
      "channel": "alarm_stream",
      "car_ui": False,
      "subtitle": "",
      "fontsize": "large",
      "position": "center",
      "duration": 10,
      "transparency": "0%",
      "interrupt": False,
      "url": "https://home.43acaciaroad.org/api/frigate/notifications/1766218266.042615-blamq9/driveway/clip.mp4",
      "attachment": {
        "url": "https://home.43acaciaroad.org/api/frigate/notifications/1766218266.042615-blamq9/driveway/master.m3u8",
        "content-type": "application/vnd.apple.mpegurl"
      },
      "push": {
        "sound": {
          "name": "default",
          "volume": 1.0
        },
        "interruption-level": "time-sensitive"
      },
      "entity_id": "camera.driveway",
      "actions": [
        {
          "action": "URI",
          "title": "View Clip",
          "uri": "https://home.43acaciaroad.org/api/frigate/notifications/1766218266.042615-blamq9/driveway/clip.mp4",
          "icon": "",
          "destructive": False
        },
        {
          "action": "URI",
          "title": "View Snapshot",
          "uri": "https://home.43acaciaroad.org/api/frigate/notifications/1766218266.042615-blamq9/snapshot.jpg",
          "icon": "",
          "destructive": False
        },
        {
          "action": "silence-automation.generate_apple_event_for_frigate_driveway",
          "title": "Silence New Notifications",
          "uri": "silence-automation.generate_apple_event_for_frigate_driveway",
          "icon": "",
          "destructive": True
        }
      ]
    })
    # set up local server for image, changing host name to mock server name, keeping path the same
    image_url = urlparse(uut.data["image"])
    snapshot_url = local_server.url_for(image_url.path)
    uut.data["image"] = snapshot_url
    local_server.expect_request(image_url.path).respond_with_data(sample_jpeg.contents, content_type=sample_jpeg.mime_type)  # type: ignore

    await uut.initialize()
    await uut.deliver()

    assert uut.media["snapshot_url"] == snapshot_url
    assert uut.media["clip_url"] == 'https://home.43acaciaroad.org/api/frigate/notifications/1766218266.042615-blamq9/driveway/master.m3u8'
    assert len(uut.deliveries["plain_email"]["delivered_envelopes"]) == 1
    call_data = uut.deliveries["plain_email"]["delivered_envelopes"][0].calls[0]  # type:ignore

    assert call_data.action == 'smtp'
    assert call_data.domain == 'notify'
    assert call_data.target_data is None
    assert call_data.exception is None
    assert call_data.action_data is not None
    assert call_data.action_data['message'] == 'A Car was detected on the Driveway camera.'
    assert call_data.action_data['target'] == ['joe@mctest.org']
    assert sum(1 for img in call_data.action_data['data']['images'] if img.endswith("jpeg")) == 1
