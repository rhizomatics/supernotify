# Rolling Review


## Functionality

Review the functionality across the code base, including architecture alignment with current Supernotify and Home Assistant including opportunities to simplify using newer platform features. Check also test coverage, including end to end flow gaps.  For documentation check gaps on explaining functionality, errors in text or examples. Ensure there is no user visible text, including for repairs/exceptions that is hard-coded for English and create translation keys for them.

| Function                    | Review Date   | Fix Version |
| --------------------------- | ------------- | ----------- |
| Dupe Detection              |               |             |
| Archiving                   | 30th Oct 2026 | `v2.16.2`   |
| Snoozing                    |               |             |
| Media Grab                  |               |             |
| Diagnostics                 |               |             |
| Home Assistant API          |               |             |
| Home Assistant Entities     |               |             |
| LLM and Conversation        |               |             |
| Person and User             |               |             |
| Scenarios                   |               |             |
| Multi-lingual               | 20th Oct 2026 | `v2.16.0`   |
| Transport Base and Delivery |               |             |
| Architecture Diagrams       |               |             |
| Non-HA Dependencies         |               |             |

## Transports

Review the transport, including architecture alignment with current Supernotify and Home Assistant. Check also test coverage, including end to end flow gaps.  For documentation check gaps on explaining functionality, errors in text or examples. Ensure there is no user visible text, including for repairs/exceptions that is hard-coded for English and create translation keys for them.


| Transport            | Review Date   | Fix Version |
| -------------------- | ------------- | ----------- |
| `chime`              | 19th Oct 2026 | `v2.16.0`   |
| `notify_entity`      | 19th Oct 2026 | `v2.16.0`   |
| `mobile_push`        | 20th Oct 2026 | `v2.16.0`   |
| `alexa_devices`      | 29th Oct 2026 | `v2.16.1`   |
| `alexa_media_player` | 29th Oct 2026 | `v2.16.1`   |
| `email`              | 20th Oct 2026 | `v2.16.0`   |
| `generic`            | 20th Oct 2026 | `v2.16.0`   |
| `tts`                | 29th Oct 2026 | `v2.16.1`   |
| `sms`                | 29th Oct 2026 | `v2.16.1`   |
| `mqtt`               | 29th Oct 2026 | `v2.16.1`   |
| `html5`              | 29th Oct 2026 | `v2.16.1`   |
| `media`              | 29th Oct 2026 | `v2.16.1`   |
| `telegram`           | 29th Oct 2026 | `v2.16.1`   |
| `kodi`               | 30th Oct 2026 | `v2.16.2`   |
| `discord`            | 30th Oct 2026 | `v2.16.2`   |
| `persistent`         | 30th Oct 2026 | `v2.16.2`   |
| `pushover`           | 30th Oct 2026 | `v2.16.2`   |
| `ntfy`               | 30th Oct 2026 | `v2.16.2`   |
| `lametric`           | 30th Oct 2026 | `v2.16.2`   |
| `matrix`             | 30th Oct 2026 | `v2.16.2`   |
| `gotify`             | 30th Oct 2026 | `v2.16.2`   |
