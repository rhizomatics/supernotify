# Developer Documentation

* [Concepts](concepts.md) - How a notification flows through scenarios, deliveries, targets, envelopes and transports
* [Roadmap](roadmap.md), feature and architecture [RFCs](./rfcs/index.md) and [Design Principles](principles.md)
* [Diagrams](./diagrams/index.md) - technical diagrams for data flow and architecture
* [JSON Schemas](reference/schemas/index.md)
    - Automatically generated from Home Assistant `voluptuous` Python schemas, covering both configuration and *Action* `data`
    - Also available as plain JSON Schema documents, for example [Full_Configuration.schema.json](./schemas/json/Full_Configuration.schema.json)
* [Classes](./reference/classes/index.md)
    - Most important classes used inside Supernotify
* [Transports](../reference/transports.md)
    - Table of Transport Adaptor configuration options automatically generated from current Python code

Code coverage, Home Assistant integration audit data and example renders of the provided default HTML eMail template, showing how it looks for different priority levels, are in [Reference](reference/index.md).

## Developer Shell

The [ha-repl](https://homeassistant-repl.rhizomatics.org.uk) developer shell has a custom plugins for the common Supernotify classes, like the registries, scenarios, people etc. You will need to call `ha-repl trust` in the directory to use it first, since the plugin code runs at startup.

![scenarios access](../assets/images/ha-repl_scenarios.png)

## More Developer Help

See also transport and options tables in the [Reference](../reference/index.md) section.

Find out more at the [Supernotify GitHub repo](https://github.com/rhizomatics/supernotify)
