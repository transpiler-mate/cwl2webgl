<!--
Copyright 2026 Transpiler-Mate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Plugin and API reference

## Registration

```toml
[project.entry-points."transpiler_mate.plugins"]
cwl2webgl = "cwl2webgl.plugin:cwl2webgl"
```

The plugin is registered with `transpiler_mate.api.transpiler_plugin`. Import it
and its options from `cwl2webgl.plugin`; the package root exports `__version__`.

## Options

| Python field | CLI option | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `output` | `--output` | `pathlib.Path` | `workflow.html` | Destination HTML file |
| `overwrite` | `--overwrite` | `bool` | `False` | Allow replacement of an existing destination |

`CWL2WebGLOptions` rejects unknown fields. Workflow selection and the title are
provided by `context.process_id` and `context.metadata.name`, respectively.

## Execute from a host

```python
from pathlib import Path
from transpiler_mate.api import TranspilerContext
from cwl2webgl.plugin import CWL2WebGLOptions, cwl2webgl


def export_workflow(context: TranspilerContext) -> None:
    cwl2webgl.execute(
        context,
        CWL2WebGLOptions(output=Path("workflow.html"), overwrite=True),
    )
```

The host supplies these context fields:

| Field | Use |
| --- | --- |
| `source` | Base location for relative references and view identity |
| `document` / `processes` | Already-loaded cwl-utils process objects |
| `process_id` | Optional selected workflow ID; otherwise include all workflows |
| `metadata.name` | Viewer heading and browser title |
| `resolver` | Resolves external process references into another context |

Execution returns `None` and writes the destination. The plugin reads the DOM
without modifying it. CWL 1.0, 1.1, and 1.2 DOMs are covered by the tests.

## Render without writing

`render(context, options)` returns the complete HTML as a string. It does not
write files or apply overwrite checks. The `output` and `overwrite` options are
used by plugin execution, not by rendering.

```python
from cwl2webgl.plugin import CWL2WebGLOptions, render

# context is supplied by the host.
html = render(context, CWL2WebGLOptions())
```

## Projection internals

`Projection(context).build(workflow_id=None)` returns presentation data with
`version`, `roots`, and `views`. A supplied workflow ID takes precedence over
`context.process_id`. Exact IDs are preferred; unique short IDs are accepted for
root selection. Process-reference resolution does not use basename matching.

Views contain workflow details, nodes, and edges. Nodes retain `cwlId`, `kind`,
`label`, and `details`; subworkflow nodes also reference a child view. Edges
retain source and target node IDs, exact port IDs, and binding details. This is
internal rendering data, not a separate CWL model or a stable interchange API.

## Error behavior

`PluginFailureError` reports invalid selections, no workflows, ambiguous or
recursive references, duplicate nodes or source ports, unknown connection
sources, and protected output paths.

`PluginExecutionError` wraps resolver errors and unexpected generation or I/O
errors. The original exception is retained as its cause. Existing output is
only replaced after rendering and writing the temporary file succeed. Temporary
files are cleaned up on completion or failure.

## Generated API documentation

::: cwl2webgl.plugin.CWL2WebGLOptions

::: cwl2webgl.plugin.render

::: cwl2webgl.projection.Projection
