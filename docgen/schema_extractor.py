import sys
from pathlib import Path

sys.path.append(str((Path(__file__).parent / "..").resolve()))

import json
import logging
import typing

import homeassistant.helpers.config_validation as cv
import mkdocs_gen_files
from json_schema_for_humans.generate import generate_from_schema
from json_schema_for_humans.generation_configuration import GenerationConfiguration
from voluptuous import Any
from voluptuous_openapi import convert

import custom_components.supernotify

TOP_LEVEL_SCHEMAS = {
    "SUPERNOTIFY_SCHEMA": "Platform Configuration",
    "SCENARIO_SCHEMA": "Scenario Definition",
    "ACTION_DATA_SCHEMA": "Notify Action Data",
}

# some hacks to stop voluptuous_openapi generating broken schemas


def tune_schema(node: dict[str, type | typing.Any] | list[type | typing.Any]) -> None:
    if isinstance(node, dict):
        for key in node:
            if node[key] in (cv.url, cv.string):
                node[key] = str
                logging.info(f"Converted {key} to Required(str)")
            elif node[key] == cv.boolean:
                node[key] = bool

            if isinstance(node[key], Any):
                node[key].validators = [v if v not in (cv.url, cv.string) else str for v in node[key].validators]


def walk_schema(schema: dict[str, type | typing.Any] | list[str | typing.Any]) -> None:
    tune_schema(schema)
    if isinstance(schema, dict):
        for key in schema:
            walk_schema(schema[key])
    elif isinstance(schema, list):
        for sub_schema in schema:
            walk_schema(sub_schema)


def schema_doc() -> None:
    Path("docs/schemas").mkdir(exist_ok=True)
    Path("docs/schemas/js").mkdir(exist_ok=True)

    v_schemas = {s: getattr(custom_components.supernotify, s) for s in TOP_LEVEL_SCHEMAS}
    for vol_schema in v_schemas.values():
        walk_schema(vol_schema.schema)
    j_schemas = {TOP_LEVEL_SCHEMAS[s[0]]: convert(s[1]) for s in v_schemas.items()}
    config = GenerationConfiguration(
        examples_as_yaml=True, template_name="md", show_toc=False, markdown_options={"show_heading_numbers": False}
    )

    # parser = jsonschema2md.Parser(collapse_children=True)
    for schema_name, schema in j_schemas.items():
        logging.info(f"Exporting {schema_name}")
        try:
            schema.setdefault("title", schema_name)
            schema.setdefault("$id", "https://jeyrb.github.io/hass_supernotify/schemas/" + schema_name + ".json")
            schema.setdefault("description", f"Voluptuous validation schema for {schema_name}")
            schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
            schema_filename = f"schemas/js/{schema_name}.schema.json"
            with mkdocs_gen_files.open(schema_filename, "w") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)
                schema_path = f.name

            lines = generate_from_schema(schema_path, config=config)
            doc_filename = f"schemas/{schema_name}.md"
            with mkdocs_gen_files.open(doc_filename, "w") as df:
                df.write(lines)
        except Exception:
            logging.exception(f"Error processing schema {schema_name}")
            continue


schema_doc()
