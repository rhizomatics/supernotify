import json
import logging
import sys
import typing
from pathlib import Path
from types import FunctionType

import mkdocs_gen_files
from json_schema_for_humans.generate import generate_from_schema  # type: ignore
from json_schema_for_humans.generation_configuration import GenerationConfiguration  # type: ignore
from voluptuous_openapi import convert  # type: ignore

sys.path.append(str((Path(__file__).parent / "..").resolve()))
# import must come after sys.path append
import custom_components.supernotify  # noqa: I001


ROOT_URL = "https://supernotify.rhizomatics.github.io/developer/schemas/"

TOP_LEVEL_SCHEMAS = {
    "SUPERNOTIFY_SCHEMA": "Platform Configuration",
    "SCENARIO_SCHEMA": "Scenario Definition",
    "STRICT_ACTION_DATA_SCHEMA": "Notify Action Data",
    "DELIVERY_SCHEMA": "Delivery Definition",
    "DELIVERY_CUSTOMIZE_SCHEMA": "Delivery Customization",
    "RECIPIENT_SCHEMA": "Recipient Definition",
    "CAMERA_SCHEMA": "Camera Definition",
    "TRANSPORT_SCHEMA": "Transport Definition",
    "CHIME_ALIASES_SCHEMA": "Chime Aliases Definition",
}

# some hacks to stop voluptuous_openapi generating broken schemas


def tune_schema(node: dict[str, type | typing.Any] | list[type | typing.Any]) -> None:
    def defuncify(v: typing.Any) -> typing.Any:
        if isinstance(v, FunctionType):
            if v.__name__ in ("url", "string"):
                return str
            if v.__name__ == "boolean":
                return bool
        return v

    if isinstance(node, dict):
        for key in node:
            node[key] = defuncify(node[key])
            if isinstance(node[key], FunctionType):
                if node[key].__name__ in ("url", "string"):
                    node[key] = str
                    logging.info(f"Converted {key} to Required(str)")
                elif node[key].__name__ == "boolean":
                    node[key] = bool

            if hasattr(node[key], "validators"):
                node[key].validators: list[FunctionType] = [defuncify(v) for v in node[key].validators]


def walk_schema(schema: dict[str, type | typing.Any] | list[str | typing.Any]) -> None:
    tune_schema(schema)
    if isinstance(schema, dict):
        for key in schema:
            walk_schema(schema[key])
    elif isinstance(schema, list):
        for sub_schema in schema:
            walk_schema(sub_schema)


def schema_doc() -> None:
    Path("docs/developer/schemas").mkdir(exist_ok=True)
    Path("docs/developer/schemas/js").mkdir(exist_ok=True)

    v_schemas = {s: getattr(custom_components.supernotify, s) for s in TOP_LEVEL_SCHEMAS}
    for vol_schema in v_schemas.values():
        try:
            walk_schema(vol_schema.schema)
        except Exception as e:
            logging.exception("Failed on %s: %s", vol_schema, e)
    j_schemas = {TOP_LEVEL_SCHEMAS[s[0]]: convert(s[1]) for s in v_schemas.items()}
    config = GenerationConfiguration(
        examples_as_yaml=True,
        template_name="md",
        show_toc=False,
        template_md_options={
            "show_heading_numbers": False,
            "properties_table_columns": ["Property", "Pattern", "Type", "Deprecated"],
        },
    )

    # parser = jsonschema2md.Parser(collapse_children=True)
    for schema_name, schema in j_schemas.items():
        schema_link_name = schema_name.replace(" ", "_")
        logging.info(f"Exporting {schema_name}")
        try:
            schema.setdefault("title", schema_name)
            schema.setdefault("$id", ROOT_URL + schema_link_name + ".json")
            schema.setdefault("description", f"Voluptuous validation schema for {schema_link_name}")
            schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
            schema_filename = f"developer/schemas/json/{schema_link_name}.schema.json"
            with mkdocs_gen_files.open(schema_filename, "w") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)
                schema_path = f.name

            lines = generate_from_schema(schema_path, config=config)
            doc_filename = f"developer/schemas/{schema_link_name}.md"
            with mkdocs_gen_files.open(doc_filename, "w") as df:
                df.write(lines)
        except Exception:
            logging.exception(f"Error processing schema {schema_name}")
            continue

    with mkdocs_gen_files.open("developer/schemas/index_gen.md", "w") as df:
        df.write('# JSON Schema for Supernotify\n')
        df.write('''These are auto-generated from the Home Assistant
         [voluptuous](https://github.com/alecthomas/voluptuous) schema definitions 
         for configuration and action `data` calls.\n\n''')
        df.write("## JSON Schema Files\n")
        df.write("|Schema|JSON Definition|Documentation|\n")
        df.write("|------|---------------|-------|\n")
        for schema_name in j_schemas:
            schema_link_name = schema_name.replace(" ", "_")
            df.write(f"|{schema_name}|[{schema_link_name}.json](json/{schema_link_name}.schema.json)|")
            df.write(f"[Schema Doc]({schema_link_name}.md)|\n")

        df.write("\n")


schema_doc()
