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

# Explore your first workflow

This tutorial generates a viewer for a small workflow with one input, one echo
step, and one output. You need Python 3.10 or newer and a browser with WebGL
support for the graph.

## 1. Install from a checkout

Run these commands from the repository root:

```console
python -m venv .venv
source .venv/bin/activate
python -m pip install . transpiler-mate-runtime
transpiler-mate cwl2webgl --help
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.
The runtime discovers the installed plugin and generates its command options.

## 2. Inspect the example

Open [hello.cwl](../examples/hello.cwl), located at `docs/examples/hello.cwl`
in the checkout. The `main` workflow passes `message` to the echo tool in the same packed document
and exposes its captured standard output as `greeting`.

Document-level Schema.org metadata supplies the application name, description,
authorship, and other fields validated by the runtime. The name becomes the
viewer title. Keep this metadata when adapting the example to your own workflow.

## 3. Generate the HTML

```console
transpiler-mate cwl2webgl 'docs/examples/hello.cwl#main' --output workflow.html
```

The fragment selects `main`. Generation reads the workflow structure; it does
not run echo or create a greeting file. The result is a single `workflow.html`
containing styles, scripts, and workflow data.

## 4. Explore

Open `workflow.html` directly in your browser. You should see three nodes and
two connections. Select the echo step to inspect its input and output contracts,
then select a connection to inspect its port IDs.

Use **Trace** to switch between upstream, downstream, both directions, and
selected-only highlighting. Type `echo` in **Find** to filter the node list and
highlight matching nodes. Clear the search to restore the list.

Drag a node to move it, drag empty background to pan, and scroll to zoom.
Press Escape during a drag to cancel it. **Fit graph** recenters the current
layout; **Reset layout** restores the automatic layout. Reloading the page
also discards manual positions.

Larger workflows may contain subworkflow nodes. Select one and use **Open
subworkflow**, then **Parent** to return to the caller.

## 5. Regenerate after an edit

After changing the source, explicitly allow replacement:

```console
transpiler-mate cwl2webgl 'docs/examples/hello.cwl#main' --output workflow.html --overwrite
```

Without `--overwrite`, an existing output is protected. Continue with
[CLI usage](../how-to/use-cli.md) or [Python integration](../reference/api.md).
