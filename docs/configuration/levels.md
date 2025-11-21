# Configuration Levels

## Flexible Configuration

Delivery configuration can be done in lots of different ways to suit different configurations
and to keep those configuration as minimal as possible.

| Where                               | When            | Notes                                          |
|-------------------------------------|-----------------|------------------------------------------------|
| Action Data                         | Runtime call    |                                                |
| Recipient delivery override         | Runtime call    |                                                |
| Scenario delivery override          | Runtime call    | Multiple scenarios applied in no special order |
| Delivery definition                 | Startup         | `message` and `title` override Action Data     |
| Transport Delivery Defaults         | Startup         |                                                |
| Target notification action defaults | Downstream call |                                                |

## Priority order of configuration application

1. Action Data passed at runtime call
2. Recipient delivery override
3. Scenario delivery override
4. Delivery definition
5. Transport defaults
6. Target notification action defaults, e.g. mail recipients ( this isn't applied inside Supernotify )
