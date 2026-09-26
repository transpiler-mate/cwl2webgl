<!--
Copyright 2026 Terradue

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

# Generate a viewer from the CLI

Install the plugin and `transpiler-mate-runtime` in the same environment.
The runtime owns source loading, process selection, and metadata validation.

## Render a workflow

```console
transpiler-mate cwl2webgl 'docs/examples/hello.cwl#main' --output workflow.html
```

Run this example from the repository root, or replace the source with your own
CWL location. Quote a source containing a fragment to preserve it in your shell.
Open the generated HTML directly in your browser.

## Choose which workflows to include

Append a workflow ID as a source fragment, such as `#main`, to select it.
With no selected process ID, the plugin includes all Workflow processes in the
loaded document in the dropdown. Referenced subworkflows are included as nested
views. Selecting a tool instead of a workflow fails.

```console
transpiler-mate cwl2webgl docs/examples/hello.cwl --output workflows.html
```

Workflow selection comes from the context prepared by the runtime. There is no
`--workflow-id` plugin option.

## Choose the output and replace it

The default output is `workflow.html` in the current directory. Parent directories
are created as needed. Replacement requires explicit permission:

```console
transpiler-mate cwl2webgl 'docs/examples/hello.cwl#main' --output build/viewer.html --overwrite
```

The plugin writes a temporary file beside the destination and publishes it
atomically. See [error behavior](../reference/api.md#error-behavior) for failures.

## Set the title

Set the application name in the source metadata, as shown by `s:name` in the
[example](../examples/hello.cwl). The runtime turns that into
`context.metadata.name`, which the viewer uses for its heading and browser title.
There is no `--title` plugin option. Workflow and node labels remain separate.

## Resolve generation failures

- If metadata validation fails, supply the document-level fields required by
  the runtime. Use the complete example as a starting point.
- If the source has no workflows, use a Workflow document or select a workflow
  from a packed document.
- If a referenced process cannot be loaded, check its URI and the host resolver's
  access to it. Generation may need network access even though viewing is offline.
- If the output already exists, choose another path or pass `--overwrite`.

Use `transpiler-mate cwl2webgl --help` to inspect options exposed by your installed
runtime. The [API reference](../reference/api.md) lists the plugin's own options.
