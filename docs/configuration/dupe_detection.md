# Duplicate Detection

Three duplicate detection policies are available:

1. `dupe_policy_message_title_same_or_lower_priority`
    - Suppress messages with the same message and title that appear within the time to live period, unless the newer message has a higher priority.
    - This is the default, including if there is no `dupe_check` section configured
2. `dupe_policy_message_title_same`
   -  Suppress messages with the same message and title that appear within the time to live period. Ignore priority.
3. `dupe_policy_none`
    - Don't suppress duplicate messages at all.

Messages and titles are stripped of digits and punctuation before being compared, so two messages with different counts, timestamps etc will be detected as duplicates.

## Configuration

The hashed message and title is cached, with a limit to both cache size and time the data is held. The `ttl` not only affects how much data is held in memory, it also controls after how long the same message can be repeated without being suppressed as a duplicate.

```yaml title="configuration snippet"
    dupe_check:
      ttl: 300 # default, 300 seconds == 5 minutes
      size: 100 # default 100 entries in cache
      dupe_policy: dupe_policy_message_title_same_or_lower_priority
```

## Overriding

Set `force_resend: true` on the `data` section of a notification to override any dupe detection, just for that message.
