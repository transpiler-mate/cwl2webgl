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

`cwl2webgl` is a Transpiler-Mate plugin that turns a loaded CWL workflow into an
interactive, offline HTML explorer. Browse workflow dependencies, open nested
workflows, and inspect ports and step bindings without running the workflow.

## Install and run

Requires Python 3.10 or newer. From a checkout of this repository:

```console
python -m pip install . transpiler-mate-runtime
transpiler-mate cwl2webgl 'docs/examples/hello.cwl#main' --output workflow.html
```

Open `workflow.html` directly in a browser. Use `--overwrite` to replace an
existing file. Omit the source fragment (`#main`) to include all workflows in
the loaded document in the workflow selector.

The runtime loads CWL and validates its metadata before invoking the plugin.
The included [hello workflow](docs/examples/hello.cwl) supplies that metadata.
The viewer title comes from `context.metadata.name`; the plugin options are
`output` and `overwrite`.

## Explore a workflow

- Drag nodes to rearrange them, drag the background to pan, and scroll to zoom.
  **Fit graph** recenters the view; **Reset layout** restores automatic placement.
- Search by label or CWL identifier, or select nodes using the keyboard-accessible list.
- Trace upstream, downstream, or both directions from a selected node.
- Open a subworkflow in its own view and return with **Parent**.
- Inspect contracts, defaults, formats, secondary files, requirements, bindings,
  scatter, conditions, expressions, and individual port connections.

CSS, JavaScript, and workflow data are embedded in one HTML file. Viewing it
requires no server, CDN, Java, or Node.js. The HTML inspector remains usable
when WebGL is unavailable. Layout changes survive navigation within the open
page, but are lost on reload.

The viewer shows static CWL structure. It does not execute expressions, expand
scatter invocations, or show runtime data lineage. Connections are straight and
may cross cards. The layout and interaction are intended for small to medium
workflows. The HTML embeds workflow details, so share it as you would the source.

## Python integration

```python
from pathlib import Path
from cwl2webgl.plugin import CWL2WebGLOptions, cwl2webgl

# context is a TranspilerContext prepared by your host.
cwl2webgl.execute(context, CWL2WebGLOptions(output=Path("workflow.html")))
```

The host provides the loaded cwl-utils DOM, metadata, selected process ID, and
resolver. The plugin reads those objects without modifying the DOM. The CLI
runtime is optional for hosts that already supply a context.

## Documentation

Start with the [first workflow tutorial](docs/tutorials/first-steps.md), then see
[CLI usage](docs/how-to/use-cli.md), the [API reference](docs/reference/api.md),
and [architecture](docs/explanation/architecture.md).

The published documentation is at
[Transpiler-Mate.github.io/cwl2webgl](https://Transpiler-Mate.github.io/cwl2webgl/).

## Development

With Hatch and Task installed, run:

```console
hatch run dev:typecheck
hatch run dev:lint
hatch run dev:check
hatch run dev:security
hatch run test:test
hatch build
```

The test matrix covers Python 3.10–3.14. Python tests exercise real cwl-utils
DOMs for CWL 1.0, 1.1, and 1.2; loader and runtime integration tests are optional.
Install and run the pre-commit hooks with:

```console
task quality:pre-commit:install
task quality:pre-commit:run
```

The Pattern 12 regression uses the original CWL and pinned imported schemas in
`tests/fixtures`, without network access during the test. Generate its viewer:

```console
hatch run dev:python tests/test_pattern12.py
```

This writes `examples/pattern-12.html`. The harness supplies a display name via
test metadata; it does not demonstrate the runtime's full metadata validation.
For the matching browser drag regression, install Playwright and Chromium:

```console
npm install --no-save playwright
npx playwright install chromium
node tests/drag-browser.cjs examples/pattern-12.html
```

`tests/browser.cjs` expects the older Atlas fixture, which is not included in
this checkout; it is not a generic smoke test for arbitrary generated HTML.
See [installation and documentation development](docs/how-to/install.md) for
local documentation build commands.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
