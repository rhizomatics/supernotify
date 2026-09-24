from pathlib import Path
from typing import Any
from unittest.mock import Mock

import mkdocs_gen_files
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from custom_components.supernotify.engine import TRANSPORTS
from custom_components.supernotify.model import SelectionRule
from custom_components.supernotify.options import COMMON_OPTIONS, DeliveryOption

TYPE_LABELS: dict[Any, str] = {
    cv.boolean: "bool",
    cv.string: "str",
    SelectionRule: "[Selection Rules](../configuration/selection_rules.md)",
    dict: "mapping",
    list: "list[str]",
    int: "int",
}


def esc(v: Any) -> str:  # ruff: ignore[any-type]
    return str(v).replace("|", "&#124;")


def type_label(option: DeliveryOption) -> str:
    if isinstance(option.value_type, vol.In):
        return ", ".join(f"`{value}`: {meaning}" for value, meaning in option.value_type.container.items())
    return TYPE_LABELS.get(option.value_type, getattr(option.value_type, "__name__", str(option.value_type)))


def examples_label(option: DeliveryOption) -> str:
    return "<br/>".join(f"`{esc(example)}`" for example in option.examples) if option.examples else "-"


def write_table(df: Any, options: list[DeliveryOption]) -> None:  # ruff: ignore[any-type]
    df.write("|Option|Type|Examples|Description|\n|---|---|---|---|\n")
    for option in options:
        df.write(f"|{option.key}|{type_label(option)}|{examples_label(option)}|{esc(option.description)}|\n")


def options_doc() -> None:
    doc_filename = "reference/options.md"
    mkdocs_gen_files.set_edit_path(doc_filename, "../docgen/options_table.py")
    mock_context = Mock(custom_template_path=Path())

    with mkdocs_gen_files.open(doc_filename, "w") as df:
        df.write("# Options Reference\n\n")
        df.write(
            "Every `options:` key accepted by a delivery or transport, generated from the "
            "`DeliveryOption` metadata in [options.py](https://github.com/rhizomatics/supernotify/"
            "blob/main/custom_components/supernotify/options.py). See "
            "[Default Options](../reference/transports.md#default-options) for the actual default value each "
            "transport sets for these.\n\n"
        )

        df.write("## Common Options\n\n")
        df.write("Accepted by every transport.\n\n")
        write_table(df, COMMON_OPTIONS)

        df.write("\n## Transport-Specific Options\n\n")
        for transport_class in sorted(TRANSPORTS, key=lambda t: t.name):
            if not transport_class.declared_options:
                continue
            transport = transport_class(mock_context)
            df.write(f"\n### {transport.name}\n\n")
            write_table(df, transport_class.declared_options)


options_doc()
