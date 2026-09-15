import json
import logging
import sys
import typing
from pathlib import Path
from types import FunctionType

# Home Assistant aliases the `voluptuous` module to its `probatio` replacement in
# sys.modules (see homeassistant/__init__.py's install_as_voluptuous()), but only if
# that happens before anything else imports the real `voluptuous`, so homeassistant
# has to be imported first here.
import homeassistant  # noqa: F401
import mkdocs_gen_files
from json_schema_for_humans.generate import generate_from_schema  # type: ignore
from json_schema_for_humans.generation_configuration import GenerationConfiguration  # type: ignore
from probatio import UNSUPPORTED, to_openapi


def _fixup_ha_validators(node: typing.Any) -> typing.Any:  # ruff: ignore[any-type]
    """Home Assistant's cv.url/string/boolean are plain functions typed to accept
    Any, so probatio can't infer a JSON type from their signature; recognize them
    by name instead."""
    if isinstance(node, FunctionType):
        if node.__name__ in ("url", "string"):
            return {"type": "string"}
        if node.__name__ == "boolean":
            return {"type": "boolean"}
    return UNSUPPORTED


def convert(schema: typing.Any) -> dict[str, typing.Any]:  # ruff: ignore[any-type]
    return to_openapi(schema, custom_serializer=_fixup_ha_validators)


sys.path.append(str((Path(__file__).parent / "..").resolve()))
# import must come after sys.path append
import custom_components.supernotify.schema

_LOGGER = logging.getLogger(__name__)

ROOT_URL = "https://supernotify.rhizomatics.github.io/developer/schemas/"

TOP_LEVEL_SCHEMAS = {
    "FULL_CONFIG_SCHEMA": "Full Configuration",
    "SCENARIO_SCHEMA": "Scenario Definition",
    "STRICT_ACTION_DATA_SCHEMA": "Notify Action Data",
    "NOTIFY_ACTION_SCHEMA": "Notify Action",
    "DELIVERY_SCHEMA": "Delivery Definition",
    "DELIVERY_CUSTOMIZE_SCHEMA": "Delivery Customization",
    "RECIPIENT_SCHEMA": "Recipient Definition",
    "CAMERA_SCHEMA": "Camera Definition",
    "TRANSPORT_SCHEMA": "Transport Definition",
    "CHIME_ALIASES_SCHEMA": "Chime Aliases Definition",
}


def schema_doc() -> None:
    Path("docs/developer/schemas").mkdir(exist_ok=True)
    Path("docs/developer/schemas/js").mkdir(exist_ok=True)

    v_schemas = {s: getattr(custom_components.supernotify.schema, s) for s in TOP_LEVEL_SCHEMAS}
    j_schemas = {s[0]: (TOP_LEVEL_SCHEMAS[s[0]], convert(s[1])) for s in v_schemas.items()}
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
    for schema_id, (schema_name, schema) in j_schemas.items():
        schema_link_name = schema_name.replace(" ", "_")
        _LOGGER.info(f"Exporting {schema_name}")
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
            mkdocs_gen_files.set_edit_path(
                doc_filename,
                f"https://github.com/search?q=repo%3Arhizomatics%2Fsupernotify+path%3Acustom_components%2Fsupernotify%2F__init__.py+{schema_id}&type=code",
            )
        except Exception:
            _LOGGER.exception(f"Error processing schema {schema_name}")
            continue

    with mkdocs_gen_files.open("developer/schemas/index.md", "w") as df:
        df.write("# JSON Schema for Supernotify\n")
        df.write("""These are auto-generated from the Home Assistant
         [voluptuous](https://github.com/alecthomas/voluptuous) schema definitions
         for configuration and action `data` calls.\n\n""")
        df.write("## JSON Schema Files\n")
        df.write("|Schema|JSON Definition|Documentation|\n")
        df.write("|------|---------------|-------|\n")
        for schema_name in j_schemas:
            schema_link_name = schema_name.replace(" ", "_")
            df.write(f"|{schema_name}|[{schema_link_name}.json](json/{schema_link_name}.schema.json)|")
            df.write(f"[Schema Doc]({schema_link_name}.md)|\n")

        df.write("\n")

    mkdocs_gen_files.set_edit_path("developer/schemas/index.md", "../docgen/schema_extractor.py")


schema_doc()
