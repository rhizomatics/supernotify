# Removing Supernotify

Source: https://supernotify.rhizomatics.org.uk/latest/quick_start/removing/

Go to **Settings → Marketplace**, open **Supernotify**, and choose **Uninstall** from the three dots menu. It can't be uninstalled while it's still set up, so either remove it from **Settings → Devices & Services** first, or choose **Delete and uninstall**, which also deletes its devices and entities.

Before Home Assistant 2026.11, from the HACS menu, select `Supernotify` and choose `Remove` from the `...` menu.

### Cleaning Up Config

1. Any manually created YAML files in the `config` directory will be untouched, remove these manually if confident they won't be needed again.
1. Any archived notifications will remain, by default in `/config/archive/supernotify` directory unless configured otherwise. Remove this directory if needed.
1. If using cameras or image attachments, media files may be left, by default in `/config/media/supernotify` directory unless configured otherwise. Remove this directory if needed.
1. Templates may be left behind, by default in a `supernotify/templates` directory under your Home Assistant config directory unless configured otherwise. Remove this directory if needed.
