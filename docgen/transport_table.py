from pathlib import Path
from typing import Any
from unittest.mock import Mock

import mkdocs_gen_files

from custom_components.supernotify.notify import TRANSPORTS


def esc(v: Any) -> str:
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
        df.write("## Configuration Options\n")
        df.write(f"|Transport|Features|{'|'.join(option_keys)}|\n")
        df.write(f"|---------|--------|{'-------|' * len(option_keys)}\n")
        for transport_class in TRANSPORTS:
            transport = transport_class(Mock(template_path=Path()))
            options = transport.default_config.delivery_defaults.options
            features: list[str] = [f.name for f in transport.supported_features]
            df.write(f"|{transport.name}|{', '.join(features)}")
            df.write(f"|{'|'.join(esc(options.get(k, '-')) for k in option_keys)}|\n")

        df.write("\n")


transport_doc()
