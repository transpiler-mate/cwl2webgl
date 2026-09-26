# Copyright 2026 Terradue
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

from __future__ import annotations

import copy
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from cwl_utils.parser import LoadingOptions, Process, Workflow, load_document_by_yaml
from cwl_utils.parser import cwl_v1_2 as cwl
from pydantic import AnyUrl, ValidationError
from transpiler_mate.api import (
    PluginExecutionError,
    PluginFailureError,
    SoftwareApplication,
    TranspilerContext,
)

from cwl2webgl.plugin import CWL2WebGLOptions, cwl2webgl, render
from cwl2webgl.projection import Projection


class Resolver:
    """Record resolution requests and return a configured context."""

    def __init__(self, result: TranspilerContext | None = None) -> None:
        self.result = result
        self.calls: list[str] = []

    def resolve(self, location: str) -> TranspilerContext:
        """Record the location and return the context, or raise OSError."""
        self.calls.append(location)
        if self.result is None:
            raise OSError("unavailable")
        return self.result


def context(
    processes: Process | Sequence[Process],
    resolver: Resolver | None = None,
    source: str = "file:///example.cwl",
    process_id: str | None = None,
) -> TranspilerContext:
    """Wrap CWL processes in a context with a recording resolver."""
    processes = processes if isinstance(processes, Sequence) else [processes]
    return TranspilerContext(
        source=AnyUrl(source),
        process_id=process_id,
        document={p.id: p for p in processes},
        metadata=SoftwareApplication.model_construct(name="Example workflow"),
        resolver=resolver or Resolver(),
    )


def document(version: str = "v1.2") -> dict[str, object]:
    """Return a minimal workflow fixture for the requested CWL version."""
    return {
        "cwlVersion": version,
        "class": "Workflow",
        "id": "main",
        "inputs": {"value": "string"},
        "outputs": {"value": {"type": "string", "outputSource": "echo/result"}},
        "steps": {
            "echo": {
                "in": {"value": "value"},
                "out": ["result"],
                "run": {
                    "class": "CommandLineTool",
                    "baseCommand": "echo",
                    "inputs": {"value": "string"},
                    "outputs": {"result": {"type": "string", "outputBinding": {"glob": "*.txt"}}},
                },
            }
        },
    }


def loaded(version: str = "v1.2") -> Workflow:
    """Load the fixture and verify it is a workflow."""
    workflow = load_document_by_yaml(
        document(version),
        "file:///example.cwl",
        loadingOptions=LoadingOptions(no_link_check=True),
    )

    assert isinstance(workflow, Workflow)
    return workflow


def root(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the first view from the projection presentation payload."""
    view = payload["views"][payload["roots"][0]]
    assert isinstance(view, dict)
    return view


@pytest.mark.parametrize("version", ["v1.0", "v1.1", "v1.2"])
def test_real_dom_all_versions_and_unchanged(version: str) -> None:
    workflow = loaded(version)
    before = copy.deepcopy(workflow.save())
    result = root(Projection(context(workflow)).build())
    expected_node_count = 3
    assert len(result["nodes"]) == expected_node_count
    expected_edge_count = 2
    assert len(result["edges"]) == expected_edge_count
    # Input and output share a local name but must have distinct node IDs.
    assert len({n["id"] for n in result["nodes"]}) == expected_node_count
    step = next(n for n in result["nodes"] if n["kind"] == "step")
    assert step["details"]["inputs"][0]["type"] == "string"
    assert step["details"]["outputs"][0]["outputBinding"]["glob"] == "*.txt"
    assert workflow.save() == before


def test_registration_and_options() -> None:
    assert cwl2webgl.name == "cwl2webgl"
    assert cwl2webgl.options_model is CWL2WebGLOptions
    assert CWL2WebGLOptions().output == Path("workflow.html")
    assert CWL2WebGLOptions().overwrite is False
    with pytest.raises(ValidationError):
        CWL2WebGLOptions.model_validate({"unknown": True})


def test_normalized_dom_with_reused_output_names() -> None:
    tool = cwl.CommandLineTool(id="tool", inputs=[], outputs=[])
    wf = cwl.Workflow(
        id="main",
        inputs=[cwl.WorkflowInputParameter(id="value", type_="string")],
        outputs=[cwl.WorkflowOutputParameter(id="value", type_="string", outputSource="b/result")],
        steps=[
            cwl.WorkflowStep(
                id="a",
                in_=[cwl.WorkflowStepInput(id="x", source="value")],
                out=["result"],
                run="#tool",
            ),
            cwl.WorkflowStep(
                id="b",
                in_=[cwl.WorkflowStepInput(id="x", source="a/result")],
                out=["result"],
                run="#tool",
            ),
        ],
    )
    result = root(Projection(context([wf, tool])).build())
    expected_edge_count = 3
    assert len(result["edges"]) == expected_edge_count
    assert result["edges"][-1]["sourcePort"] == "b/result"


def test_multi_source_scatter_conditions_and_default_only_inputs() -> None:
    wf = loaded()
    step = wf.steps[0]
    step.in_[0].source = [wf.inputs[0].id, wf.inputs[0].id]
    step.in_[0].linkMerge = "merge_flattened"
    step.in_[0].pickValue = "all_non_null"
    step.in_[0].valueFrom = "$(self)"
    step.in_.append(cwl.WorkflowStepInput(id="constant", default="fixed"))
    step.scatter = step.in_[0].id
    step.scatterMethod = "dotproduct"
    step.when = "$(true)"
    result = root(Projection(context(wf)).build())
    expected_edge_count = 3
    assert len(result["edges"]) == expected_edge_count
    assert result["edges"][0]["binding"]["linkMerge"] == "merge_flattened"
    node = next(n for n in result["nodes"] if n["kind"] == "step")
    assert node["details"]["when"] == "$(true)"
    assert node["details"]["scatterMethod"] == "dotproduct"
    assert node["details"]["bindings"][-1]["default"] == "fixed"


def test_repeated_subworkflow_and_workflow_selection() -> None:
    inner = cwl.Workflow(id="inner", inputs=[], outputs=[], steps=[])
    outer = cwl.Workflow(
        id="outer",
        inputs=[],
        outputs=[],
        steps=[
            cwl.WorkflowStep(id="first", in_=[], out=[], run="#inner"),
            cwl.WorkflowStep(id="second", in_=[], out=[], run="#inner"),
        ],
    )
    ctx = context([outer, inner])
    payload = Projection(ctx).build("outer")
    expected_workflow_count = 2
    assert len(payload["views"]) == expected_workflow_count
    nodes = root(payload)["nodes"]
    assert nodes[0]["child"] == nodes[1]["child"]
    assert len(Projection(ctx).build()["roots"]) == expected_workflow_count
    assert root(Projection(context([outer, inner], process_id="inner")).build())["id"] == "inner"


def test_external_resolver_cached_and_base_resolved() -> None:
    inner = cwl.Workflow(id="file:///other.cwl#inner", inputs=[], outputs=[], steps=[])
    resolver = Resolver(context(inner, source="file:///other.cwl"))
    outer = cwl.Workflow(
        id="main",
        inputs=[],
        outputs=[],
        steps=[
            cwl.WorkflowStep(id="first", in_=[], out=[], run="other.cwl#inner"),
            cwl.WorkflowStep(id="second", in_=[], out=[], run="other.cwl#inner"),
        ],
    )
    payload = Projection(context(outer, resolver)).build()
    assert resolver.calls == ["file:///other.cwl#inner"]
    expected_workflow_count = 2
    assert len(payload["views"]) == expected_workflow_count


def test_external_fragment_does_not_match_local_process() -> None:
    inner = cwl.Workflow(id="inner", inputs=[], outputs=[], steps=[])
    wf = cwl.Workflow(
        id="main",
        inputs=[],
        outputs=[],
        steps=[cwl.WorkflowStep(id="call", in_=[], out=[], run="file:///other.cwl#inner")],
    )
    resolver = Resolver(context(inner, source="file:///other.cwl"))
    Projection(context([wf, inner], resolver)).build("main")
    assert resolver.calls == ["file:///other.cwl#inner"]


def test_resolver_failure_has_cause() -> None:
    wf = loaded()
    wf.steps[0].run = "file:///missing.cwl"
    with pytest.raises(PluginExecutionError, match="Cannot resolve") as caught:
        Projection(context(wf)).build()
    assert isinstance(caught.value.__cause__, OSError)


@pytest.mark.parametrize("selected", ["missing", "echo"])
def test_unknown_or_non_workflow_selection(selected: str) -> None:
    with pytest.raises(PluginFailureError, match="Workflow ID"):
        Projection(context(loaded())).build(selected)


def test_no_workflow() -> None:
    with pytest.raises(PluginFailureError, match="no Workflow"):
        Projection(context(cwl.CommandLineTool(id="tool", inputs=[], outputs=[]))).build()


def test_ambiguous_short_selector() -> None:
    ctx = context(
        [
            cwl.Workflow(id="file:///a.cwl#main", inputs=[], outputs=[], steps=[]),
            cwl.Workflow(id="file:///b.cwl#main", inputs=[], outputs=[], steps=[]),
        ]
    )
    with pytest.raises(PluginFailureError):
        Projection(ctx).build("main")


def test_recursion_rejected() -> None:
    wf = cwl.Workflow(
        id="main",
        inputs=[],
        outputs=[],
        steps=[cwl.WorkflowStep(id="self", in_=[], out=[], run="#main")],
    )
    with pytest.raises(PluginFailureError, match="Recursive"):
        Projection(context(wf)).build()


def test_bad_source_leaves_existing_output_unchanged(tmp_path: Path) -> None:
    wf = loaded()
    wf.steps[0].in_[0].source = "unknown"
    path = tmp_path / "view.html"
    path.write_text("original")
    with pytest.raises(PluginFailureError, match="Unknown source"):
        cwl2webgl.execute(context(wf), CWL2WebGLOptions(output=path, overwrite=True))
    assert path.read_text() == "original"
    assert list(tmp_path.iterdir()) == [path]


def test_html_safety_and_unicode() -> None:
    wf = loaded()
    wf.label = '</script><script>alert("bad")</script> À'
    ctx = context(wf)
    ctx.metadata.name = wf.label
    page = render(ctx, CWL2WebGLOptions())
    assert wf.label not in page
    match = re.search(r'<script id="payload" type="application/json">(.*?)</script>', page, re.S)
    assert match is not None
    assert json.loads(match.group(1))["title"] == wf.label
    assert "https://cdn" not in page
    assert "__PAYLOAD__" not in page


def test_atomic_output_and_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "view.html"
    ctx = context(loaded())
    cwl2webgl.execute(ctx, CWL2WebGLOptions(output=path))
    assert path.read_text().startswith("<!doctype html>")
    with pytest.raises(PluginFailureError, match="Output exists"):
        cwl2webgl.execute(ctx, CWL2WebGLOptions(output=path))
    ctx.metadata.name = "Replacement"
    cwl2webgl.execute(ctx, CWL2WebGLOptions(output=path, overwrite=True))
    assert '"title": "Replacement"' in path.read_text()
    assert list(path.parent.iterdir()) == [path]


def test_io_error_has_cause(tmp_path: Path) -> None:
    parent = tmp_path / "file"
    parent.write_text("not a directory")
    with pytest.raises(PluginExecutionError) as caught:
        cwl2webgl.execute(context(loaded()), CWL2WebGLOptions(output=parent / "view.html"))
    assert isinstance(caught.value.__cause__, OSError)


def test_atomic_failure_cleans_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object) -> None:
        raise OSError("disk failure")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(PluginExecutionError):
        cwl2webgl.execute(
            context(loaded()),
            CWL2WebGLOptions(output=tmp_path / "view.html", overwrite=True),
        )
    assert not list(tmp_path.iterdir())


def test_real_cwl_loader_normalization(tmp_path: Path) -> None:
    loader = pytest.importorskip("cwl_loader")
    path = tmp_path / "example.cwl"
    path.write_text(json.dumps(document()))
    processes = loader.load_cwl_from_location(str(path))
    result = root(Projection(context(processes)).build("main"))
    expected_edge_count = 2
    assert len(result["edges"]) == expected_edge_count
    assert result["edges"][-1]["sourcePort"] == "echo/result"


def test_runtime_cli_entrypoint(tmp_path: Path) -> None:
    pytest.importorskip("transpiler_mate.runtime")
    CliRunner = pytest.importorskip("click.testing").CliRunner
    main = pytest.importorskip("transpiler_mate.runtime.cli").main

    example = tmp_path / "example.cwl"
    workflow = document()
    workflow["label"] = "Process scenes"
    example.write_text(json.dumps(workflow))
    output = tmp_path / "example.html"
    result = CliRunner().invoke(
        main, ["cwl2webgl", str(example) + "#main", "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert "Process scenes" in output.read_text()
