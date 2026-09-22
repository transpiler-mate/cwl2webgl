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

# Architecture and scope

## From a loaded DOM to a browser view

The host loads CWL and constructs a `TranspilerContext`. The plugin reads its
existing cwl-utils DOM directly: workflow steps, embedded or referenced `run`
processes, input bindings, output ports, `source`, and `outputSource`.
It neither reparses the source nor modifies the DOM.

`Projection` keeps traversal state, a cache of resolved external references, and
presentation dictionaries. Embedded processes are reused as objects. References
within the document resolve to existing processes; external references go through
`context.resolver.resolve`. Recursive workflow references are rejected.

Each workflow definition has one view. Repeated calls to a subworkflow share that
view, while the browser keeps the navigation path back to the caller. Presentation
IDs distinguish inputs, steps, and outputs with the same local name; original CWL
IDs remain available in the inspector.

The renderer serializes the projection into the HTML template and embeds the
packaged CSS and JavaScript. JSON characters that could close the data script
are escaped. The application name comes from `context.metadata.name`.
Generation may require external source resolution; the resulting viewer makes
no network calls.

## Rendering and interaction

Native WebGL triangles draw nodes and directed connections. A Canvas2D overlay
draws labels, and HTML provides navigation and inspection controls. Tool cards
have rounded corners, subworkflows have a double outline, inputs are
parallelograms, and outputs are hexagons.

The initial layout uses deterministic dependency layers. Connections attach to
shape boundaries and follow nodes as they are dragged. There is no obstacle
routing or crossing minimization; coincident port connections can overlap.
Inspect connections individually to distinguish their bindings.

Search matches node labels and CWL IDs. The node list supports keyboard access,
and the inspector remains usable if WebGL is unavailable. Graph rendering needs
a working browser WebGL context. Layout, hit testing, and labels are intended
for small to medium workflows; WebGL alone does not ensure large-graph performance.

Manual positions are kept in memory per workflow view. They survive navigation
within the page, including repeated calls to the same subworkflow definition,
but are not saved into the HTML or retained across reloads. **Reset layout**
restores automatic placement. Escape or a cancelled drag restores its starting
position.

## Static structure and contracts

The graph has one node per workflow input, step, and output. Step ports are
shown in the inspector rather than as separate graph nodes. Bindings without a
`source`, such as default-only inputs, create no incoming dependency edge.

Scatter declarations, `when`, `valueFrom`, and other expressions are displayed
without evaluation. The viewer does not expand scatter invocations, replay an
execution, compare workflow versions, or infer actual data lineage. Repeated
subworkflow calls represent a shared definition, not runtime invocation instances.

Subworkflows open in a focused view. Their inspector shows the declared inner
contract; inspect the calling step to see caller bindings. The HTML embeds
contracts, expressions, and referenced process details, so it should be shared
with the same care as the CWL source.

## Output integrity

The plugin renders before publishing output, writes a temporary file in the
destination directory, flushes it, and publishes it atomically. Without overwrite
permission, create-if-absent publication protects against a concurrent writer.
With overwrite enabled, the temporary file replaces the destination.
