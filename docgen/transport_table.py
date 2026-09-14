from pathlib import Path
from typing import Any
from unittest.mock import Mock

import mkdocs_gen_files

from custom_components.supernotify.const import OPTION_UNIQUE_TARGETS
from custom_components.supernotify.engine import TRANSPORTS
from custom_components.supernotify.model import EntityCategory, Target


def esc(v: Any) -> str:  # ruff: ignore[any-type]
    v = "-" if v is None else v
    v = str(v) if not isinstance(v, str) else v
    return v.replace("|", "&#124;")


def format_selector_value(value: str | list[str]) -> str:
    return value if isinstance(value, str) else "/".join(value)


def format_category(category: str | EntityCategory) -> str:
    if isinstance(category, str):
        return "unqualified" if category == Target.UNKNOWN_CUSTOM_CATEGORY else esc(category)
    constraints = []
    if category.domain is not None:
        constraints.append(f"domain={format_selector_value(category.domain)}")
    if category.platform is not None:
        constraints.append(f"platform={format_selector_value(category.platform)}")
    return esc(f"entity_id ({', '.join(constraints)})" if constraints else "entity_id")


def transport_doc() -> None:
    doc_filename = "developer/transports.md"
    option_keys = []
    mock_context = Mock(custom_template_path=Path())
    for transport_class in TRANSPORTS:
        transport = transport_class(mock_context)
        option_keys.extend(transport.default_config.delivery_defaults.options.keys())
    option_keys = sorted(set(option_keys))

    mkdocs_gen_files.set_edit_path(doc_filename, "../docgen/transport_table.py")

    with mkdocs_gen_files.open(doc_filename, "w") as df:
        df.write("# Transport Configuration\n\n")
        df.write("See the [Options Table](../transports/index.md/#table-of-options) for a description of each option.\n\n")

        df.write("## Default Inclusion\n")

        df.write("|Transport|Rank|Target Required|Inclusion|Features|\n")
        df.write("|---------|----|---------------|---------|--------|\n")
        for transport_class in sorted(TRANSPORTS, key=lambda t: t.name):
            transport = transport_class(mock_context)
            features: list[str] = [f.name for f in transport.supported_features]
            df.write(f"|[{transport.name}](../transports/{transport.name}.md)")
            df.write(f"|{transport.default_config.delivery_defaults.selection_rank}")
            df.write(f"|{transport.default_config.delivery_defaults.target_required}")
            df.write(f"|{', '.join(transport.inclusion_mode)}")
            df.write(f"|{', '.join(features)}|\n")

        df.write("\n")
        df.write("## Target Categories\n")
        df.write(
            "Which target categories each transport accepts - see [Targets](../usage/targets.md) for how to "
            "qualify a target with one. A transport with none listed relies entirely on its own name, its "
            "deliveries' names, or a delivery's `target_categories` option (e.g. `generic`).\n\n"
        )

        df.write("|Transport|Target Categories|Unique Targets|\n")
        df.write("|---------|------------------|--------------|\n")
        for transport_class in sorted(TRANSPORTS, key=lambda t: t.name):
            transport = transport_class(mock_context)
            categories = ", ".join(format_category(c) for c in transport.target_categories) or "-"
            df.write(
                f"|[{transport.name}](../transports/{transport.name}.md)|{categories}|{transport.default_config.delivery_defaults.options.get(OPTION_UNIQUE_TARGETS, False)}|\n"
            )

        df.write("\n")
        df.write("## Default Options\n")

        df.write(f"|Transport|{'|'.join(option_keys)}|\n")
        df.write(f"|---------|{'-------|' * len(option_keys)}\n")
        for transport_class in sorted(TRANSPORTS, key=lambda t: t.name):
            transport = transport_class(mock_context)
            options = transport.default_config.delivery_defaults.options
            df.write(f"|[{transport.name}](../transports/{transport.name}.md)")
            df.write(f"|{'|'.join(esc(options.get(k, 'N/A')) for k in option_keys)}|\n")

        df.write("\n")


transport_doc()
