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

# CWL to WebGL

`cwl2webgl` turns a loaded CWL workflow into a self-contained HTML explorer.
Follow dependencies, inspect input and output contracts, and navigate nested
workflows in your browser. Generated pages work offline without a web server.

## Try it

From a checkout, install the plugin and CLI runtime, then render the included example:

```console
python -m pip install . transpiler-mate-runtime
transpiler-mate cwl2webgl 'docs/examples/hello.cwl#main' --output workflow.html
```

Open `workflow.html` in your browser. The [first steps tutorial](tutorials/first-steps.md)
walks through the example and the viewer controls.

## Find what you need

- [Tutorials](tutorials/index.md): generate and explore your first workflow.
- [How-to guides](how-to/index.md): install the plugin, select workflows, and replace output.
- [Reference](reference/index.md): options, Python integration, and failure behavior.
- [Explanation](explanation/index.md): DOM traversal, rendering, and scope.

## What the viewer shows

Inputs, processing steps, subworkflows, and outputs have distinct shapes.
Select a node to trace dependencies and inspect its contracts, expressions,
scatter declarations, conditions, and bindings. Connections retain their exact
source and target port IDs. Search and the node list provide another way to
navigate; the HTML inspector remains usable without WebGL.

This is a static data-flow view. Expressions and conditions are displayed, never
executed. Node positions remain in memory while the page is open and reset on
reload. See [architecture and limitations](explanation/architecture.md) for details.
