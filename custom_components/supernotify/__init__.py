"""The Supernotify integration"""

from homeassistant.const import Platform

DOMAIN = "supernotify"

PLATFORMS = [Platform.NOTIFY]
TEMPLATE_DIR: str = "/config/templates/supernotify"
MEDIA_DIR: str = "supernotify/media"
