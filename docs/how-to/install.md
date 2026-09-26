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

# Install the plugin

Use Python 3.10 or newer. The package uses a Git-based `transpiler-mate-api`
dependency, so installation requires Git and access to the dependency repository.
The installed dependency set includes cwl-utils and Pydantic through the API,
and the plugin declares Loguru directly.

## Install from source

```console
git clone https://github.com/Transpiler-Mate/cwl2webgl
cd cwl2webgl
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Use `python -m pip install -e .` for an editable development install.
On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Add the command-line runtime

Install the runtime in the same environment as the plugin:

```console
python -m pip install transpiler-mate-runtime
transpiler-mate --help
transpiler-mate cwl2webgl --help
```

The command is provided by Transpiler-Mate's runtime; this distribution registers
its `cwl2webgl` plugin entry point. If it is missing from help, check that the
runtime and plugin are installed in the same Python environment.

For a local runtime checkout, install that checkout with
`python -m pip install ../transpiler-mate-runtime` instead.
A Python host that already constructs `TranspilerContext` does not need the CLI.

## Build the documentation

From the repository root, install the documentation tools into your environment:

```console
python -m pip install mkdocs mkdocstrings[python] pymdown-extensions
mkdocs build --strict -f mkdocs.yaml
mkdocs serve -f mkdocs.yaml
```

The configuration reads API documentation from `src`. Build output goes to
`site/`; `serve` provides a local preview. See the repository README for Hatch
quality checks and the Python test matrix.
