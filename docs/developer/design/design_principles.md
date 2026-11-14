# Design Principles

The principles supernotify is designed by. They start from the [Rhizomatics HQ policies](https://hq.rhizomatics.org.uk/policies/) that every
product follows. Sections specific to supernotify are added here as its design settles, usually through an RFC.

## Scope

supernotify: Advanced notification grouping, routing and alternative channels for Home Assistant.

It does one job and leaves the rest to Home Assistant and other integrations. Where a feature could live in
Home Assistant core, another integration or here, the RFC for it says why it belongs here.

## Home Assistant alignment

supernotify aims to be an exemplary Home Assistant citizen ([Home Assistant alignment](https://hq.rhizomatics.org.uk/policies/hass-alignment/)):

- Configured through the UI (config flow), with YAML kept only for power-user content that is naturally text and
  round-trips with the UI.
  Exception: scenarios and deliveries can also be written in YAML, since they're power-user content that is naturally text.
- Assessed against the [Integration Quality Scale](https://www.home-assistant.io/docs/quality_scale/), aiming for
  the highest level and keeping the way open to move from Marketplace to core.
- Supports a rolling 6 months of Home Assistant releases ([project standards](https://hq.rhizomatics.org.uk/policies/project_standards/)), and the
  Python versions they need ([Python versions](https://hq.rhizomatics.org.uk/policies/python_versions/)).
- Takes up new Home Assistant features within the month they're released, without dropping older supported
  versions.

## How the design changes

- Major changes are planned as RFCs in `docs/developer/design/rfcs/` ([design policy](https://hq.rhizomatics.org.uk/policies/design/)). They're
  listed with every other Rhizomatics product's on the [HQ RFCs page](https://hq.rhizomatics.org.uk/rfcs/).
- Expected work, large and small, is summarised in the roadmap.
- Releases follow the [release policy](https://hq.rhizomatics.org.uk/policies/release/): semantic versions, immutable, built and published by
  GitHub Actions.
- Everything else follows the [project standards](https://hq.rhizomatics.org.uk/policies/project_standards/) shared by all Rhizomatics repos.
