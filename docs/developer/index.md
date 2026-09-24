# Developer Documentation

* [Concepts](concepts.md) - How a notification flows through scenarios, deliveries, targets, envelopes and transports
* [Roadmap](roadmap.md), [RFCs](rfcs/index.md) and [Design Principles](principles.md)
* [Schemas](schemas/index.md)
    - Automatically generated from Home Assistant `voluptuous` Python schemas, covering both configuration and *Action* `data`
    - Also available as plain JSON Schema documents, for example [Full_Configuration.schema.json](./schemas/json/Full_Configuration.schema.json)
* [Classes](./reference/classes/index.md)
    - Most important classes used inside Supernotify
* [Class Diagram](./class_diagram.md)
    - Mermaid diagram of Core Concepts
* [Transports](../reference/transports.md)
    - Table of Transport Adaptor configuration options automatically generated from current Python code

Code coverage, Home Assistant integration audit data and example renders of the provided default HTML eMail template, showing how it looks for different priority levels, are in [Reference](reference/index.md).

See also transport and options tables in the [Reference](../reference/index.md) section.

Find out more at the [Supernotify GitHub repo](https://github.com/rhizomatics/supernotify)
