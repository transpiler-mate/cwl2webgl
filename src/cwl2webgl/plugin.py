# Copyright 2026 Transpiler-Mate
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""transpiler-mate plugin for CWL to WebGL."""

from __future__ import annotations

import json
import os
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from transpiler_mate.api import (
    PluginExecutionError,
    PluginFailureError,
    transpiler_plugin,
)

from .projection import Projection

if TYPE_CHECKING:
    from transpiler_mate.api import TranspilerContext


class CWL2WebGLOptions(BaseModel):
    """Options accepted by the CWL to WebGL plugin."""

    model_config = ConfigDict(extra="forbid")

    output: Path = Field(default=Path("workflow.html"), description="Output HTML file")
    overwrite: bool = Field(
        default=False, description="Replace an existing output file"
    )


def render(context: TranspilerContext, options: CWL2WebGLOptions) -> str:
    payload = Projection(context).build(context.process_id)
    payload["title"] = context.metadata.name
    # JSON inside an HTML script element must not contain an HTML closing tag.
    encoded = (
        json.dumps(payload, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    assets = files("cwl2webgl").joinpath("assets")
    template = assets.joinpath("viewer.html").read_text(encoding="utf-8")
    return (
        template.replace(
            "/*__STYLE__*/", assets.joinpath("viewer.css").read_text(encoding="utf-8")
        )
        .replace(
            "/*__SCRIPT__*/", assets.joinpath("viewer.js").read_text(encoding="utf-8")
        )
        .replace("__PAYLOAD__", encoded)
    )


@transpiler_plugin(
    name="cwl2webgl",
    description="Explore CWL workflows in an offline WebGL HTML viewer.",
    options_model=CWL2WebGLOptions,
)
def cwl2webgl(context: TranspilerContext, options: CWL2WebGLOptions) -> None:
    temporary: Path | None = None
    try:
        if options.output.exists() and not options.overwrite:
            raise PluginFailureError(
                f"Output exists: {options.output}; set overwrite=true to replace it"
            )
        content = render(context, options)
        options.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=options.output.parent,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if options.overwrite:
            temporary.replace(options.output)
        else:
            # Atomic create-if-absent; do not clobber a concurrent writer.
            try:
                os.link(temporary, options.output)
            except FileExistsError as exc:
                raise PluginFailureError(f"Output exists: {options.output}") from exc
    except (PluginFailureError, PluginExecutionError):
        raise
    except Exception as exc:
        raise PluginExecutionError(
            f"Cannot generate WebGL viewer at {options.output}"
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
