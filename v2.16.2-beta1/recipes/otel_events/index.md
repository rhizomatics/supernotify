# Recipe - OTEL Event Generation

Source: https://supernotify.rhizomatics.org.uk/latest/recipes/otel_events/

## Purpose

Debug issues with notifications by sending the archived notification details and traces to an OpenTelemetry logging (OTLP) aggregator.

Consolidate the notification events with Home Assistant's own system logs, so full context available for any issues - all without any YAML config if using [Remote Logger](https://remote-logger.rhizomatics.org.uk).

## Implementation

### 1. Switch on event archiving

In the Supernotify integration's options, under *Configure → Archive*, turn on archiving and, in the *Event* section, choose the outcomes to send as events. In this example not all notifications are sent, successful and partial deliveries are ignored, so pick *No Delivery*, *Fallback Delivery* and *Error*.

See [Archiving](https://supernotify.rhizomatics.org.uk/latest/configuration/archiving/#event-generation) for the options, and for keeping the events out of the recorder database.

### 2. Configure Remote Logger

Install the HACS component [Remote Logger](https://remote-logger.rhizomatics.org.uk) and set up OTLP with your log aggregator as the destination.

In the Home Assistant integration dialog, select custom event generation, and add `supernotification`.

### If you don't have a log aggregator

[OpenObserve](https://openobserve.ai) has a free, open source logging service that natively supports OTLP without the need for an ingestion tool like Vector or Fluentd, and will run in Docker. See *Remote Logger* for some example configurations.

Many other logging ingestors, transformers, databases and more are available, too many to name.

## Variations

- *Remote Logger* makes it easy to also send off Syslog messages, if an OTLP aggregator not available.
- *Remote Logger* can also generate OTLP or Syslog events for any, or indeed all, Home Assistant events, so full log context available including service calls and even state changes.
