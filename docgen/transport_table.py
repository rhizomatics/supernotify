from pathlib import Path
from typing import Any
from unittest.mock import Mock

import mkdocs_gen_files

from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.transport import Transport


def esc(v: Any) -> str:
    v = "-" if v is None else v
    v = str(v) if not isinstance(v, str) else v
    return v.replace("|", "&#124;")


def transport_doc() -> None:
    doc_filename = "developer/transports.md"
    option_keys = []
    for transport_class in TRANSPORTS:
        transport = transport_class(Mock(template_path=Path()))
        option_keys.extend(transport.default_config.delivery_defaults.options.keys())
    option_keys = sorted(set(option_keys))

    with mkdocs_gen_files.open(doc_filename, "w") as df:
        df.write("# Transport Configuration\n\n")
        df.write("See the [Options Table](../transports/index.md/#table-of-options) for a description of each option.\n\n")

        df.write("## Default Selection\n")

        df.write("|Transport|Rank|Target Required|Auto Default Delivery|Features|\n")
        df.write("|---------|----|---------------|---------------------|--------|\n")
        for transport_class in sorted(TRANSPORTS, key=lambda t: t.name):
            transport = transport_class(Mock(template_path=Path()))
            features: list[str] = [f.name for f in transport.supported_features]
            df.write(f"|[{transport.name}](../transports/{transport.name}.md)")
            df.write(f"|{transport.default_config.delivery_defaults.selection_rank}")
            df.write(f"|{transport.default_config.delivery_defaults.target_required}")
            df.write(f"|{transport.auto_configure.__func__ != Transport.auto_configure}")
            df.write(f"|{', '.join(features)}|\n")

        df.write("\n")
        df.write("## Default Options\n")

        df.write(f"|Transport|{'|'.join(option_keys)}|\n")
        df.write(f"|---------|{'-------|' * len(option_keys)}\n")
        for transport_class in sorted(TRANSPORTS, key=lambda t: t.name):
            transport = transport_class(Mock(template_path=Path()))
            options = transport.default_config.delivery_defaults.options
            df.write(f"|[{transport.name}](../transports/{transport.name}.md)")
            df.write(f"|{'|'.join(esc(options.get(k, 'N/A')) for k in option_keys)}|\n")

        df.write("\n")
        df.write("## Automatic Device Discovery\n")

        df.write("|Transport|Device Discovery|Device Domain|Device Model Exclude|\n")
        df.write("|---------|----------------|-------------|--------------------|\n")
        for transport_class in sorted(TRANSPORTS, key=lambda t: t.name):
            transport = transport_class(Mock(template_path=Path()))
            if transport.default_config.device_discovery:
                transport = transport_class(Mock(template_path=Path()))
                df.write(f"|[{transport.name}](../transports/{transport.name}.md)")
                df.write(f"|{transport.default_config.device_discovery}")
                df.write(f"|{','.join(transport.default_config.device_domain or [])}")
                df.write(f"|{','.join(transport.default_config.device_model_exclude or [])}|\n")

        df.write("\n")


transport_doc()
