from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
from cwl_utils.parser import cwl_v1_2 as cwl
from cwl_utils.parser import load_document_by_yaml
from pydantic import ValidationError
from transpiler_mate.api import (
    PluginExecutionError,
    PluginFailureError,
    SoftwareApplication,
    TranspilerContext,
)

from cwl2webgl.plugin import CWL2WebGLOptions, cwl2webgl, render
from cwl2webgl.projection import Projection


class Resolver:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def resolve(self, location):
        self.calls.append(location)
        if self.result is None:
            raise OSError("unavailable")
        return self.result


def context(processes, resolver=None, source="file:///example.cwl", process_id=None):
    processes = processes if isinstance(processes, list) else [processes]
    return TranspilerContext(
        source=source,
        process_id=process_id,
        document={p.id: p for p in processes},
        metadata=SoftwareApplication.model_construct(name="Example workflow"),
        resolver=resolver or Resolver(),
    )


def document(version="v1.2"):
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
                    "outputs": {
                        "result": {"type": "string", "outputBinding": {"glob": "*.txt"}}
                    },
                },
            }
        },
    }


def loaded(version="v1.2"):
    return load_document_by_yaml(
        document(version),
        "file:///example.cwl",
        loadingOptions=cwl.LoadingOptions(no_link_check=True),
    )


def root(payload):
    return payload["views"][payload["roots"][0]]


@pytest.mark.parametrize("version", ["v1.0", "v1.1", "v1.2"])
def test_real_dom_all_versions_and_unchanged(version):
    workflow = loaded(version)
    before = copy.deepcopy(workflow.save())
    result = root(Projection(context(workflow)).build())
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2
    assert len({n["id"] for n in result["nodes"]}) == 3  # input/output share local name
    step = next(n for n in result["nodes"] if n["kind"] == "step")
    assert step["details"]["inputs"][0]["type"] == "string"
    assert step["details"]["outputs"][0]["outputBinding"]["glob"] == "*.txt"
    assert workflow.save() == before


def test_registration_and_options():
    assert cwl2webgl.name == "cwl2webgl"
    assert cwl2webgl.options_model is CWL2WebGLOptions
    assert CWL2WebGLOptions().output == Path("workflow.html")
    assert CWL2WebGLOptions().overwrite is False
    with pytest.raises(ValidationError):
        CWL2WebGLOptions(unknown=True)


def test_normalized_dom_with_reused_output_names():
    tool = cwl.CommandLineTool(id="tool", inputs=[], outputs=[])
    wf = cwl.Workflow(
        id="main",
        inputs=[cwl.WorkflowInputParameter(id="value", type_="string")],
        outputs=[
            cwl.WorkflowOutputParameter(
                id="value", type_="string", outputSource="b/result"
            )
        ],
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
    assert len(result["edges"]) == 3
    assert result["edges"][-1]["sourcePort"] == "b/result"


def test_multi_source_scatter_conditions_and_default_only_inputs():
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
    assert len(result["edges"]) == 3
    assert result["edges"][0]["binding"]["linkMerge"] == "merge_flattened"
    node = next(n for n in result["nodes"] if n["kind"] == "step")
    assert node["details"]["when"] == "$(true)"
    assert node["details"]["scatterMethod"] == "dotproduct"
    assert node["details"]["bindings"][-1]["default"] == "fixed"


def test_repeated_subworkflow_and_workflow_selection():
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
    assert len(payload["views"]) == 2
    nodes = root(payload)["nodes"]
    assert nodes[0]["child"] == nodes[1]["child"]
    assert len(Projection(ctx).build()["roots"]) == 2
    assert (
        root(Projection(context([outer, inner], process_id="inner")).build())["id"]
        == "inner"
    )


def test_external_resolver_cached_and_base_resolved():
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
    assert len(payload["views"]) == 2


def test_external_fragment_does_not_match_local_process():
    inner = cwl.Workflow(id="inner", inputs=[], outputs=[], steps=[])
    wf = cwl.Workflow(
        id="main",
        inputs=[],
        outputs=[],
        steps=[
            cwl.WorkflowStep(id="call", in_=[], out=[], run="file:///other.cwl#inner")
        ],
    )
    resolver = Resolver(context(inner, source="file:///other.cwl"))
    Projection(context([wf, inner], resolver)).build("main")
    assert resolver.calls == ["file:///other.cwl#inner"]


def test_resolver_failure_has_cause():
    wf = loaded()
    wf.steps[0].run = "file:///missing.cwl"
    with pytest.raises(PluginExecutionError, match="Cannot resolve") as caught:
        Projection(context(wf)).build()
    assert isinstance(caught.value.__cause__, OSError)


@pytest.mark.parametrize("selected", ["missing", "echo"])
def test_unknown_or_non_workflow_selection(selected):
    with pytest.raises(PluginFailureError, match="Workflow ID"):
        Projection(context(loaded())).build(selected)


def test_no_workflow():
    with pytest.raises(PluginFailureError, match="no Workflow"):
        Projection(
            context(cwl.CommandLineTool(id="tool", inputs=[], outputs=[]))
        ).build()


def test_ambiguous_short_selector():
    ctx = context(
        [
            cwl.Workflow(id="file:///a.cwl#main", inputs=[], outputs=[], steps=[]),
            cwl.Workflow(id="file:///b.cwl#main", inputs=[], outputs=[], steps=[]),
        ]
    )
    with pytest.raises(PluginFailureError):
        Projection(ctx).build("main")


def test_recursion_rejected():
    wf = cwl.Workflow(
        id="main",
        inputs=[],
        outputs=[],
        steps=[cwl.WorkflowStep(id="self", in_=[], out=[], run="#main")],
    )
    with pytest.raises(PluginFailureError, match="Recursive"):
        Projection(context(wf)).build()


def test_bad_source_leaves_existing_output_unchanged(tmp_path):
    wf = loaded()
    wf.steps[0].in_[0].source = "unknown"
    path = tmp_path / "view.html"
    path.write_text("original")
    with pytest.raises(PluginFailureError, match="Unknown source"):
        cwl2webgl.execute(context(wf), CWL2WebGLOptions(output=path, overwrite=True))
    assert path.read_text() == "original"
    assert list(tmp_path.iterdir()) == [path]


def test_html_safety_and_unicode():
    wf = loaded()
    wf.label = '</script><script>alert("bad")</script> À'
    ctx = context(wf)
    ctx.metadata.name = wf.label
    page = render(ctx, CWL2WebGLOptions())
    assert wf.label not in page
    encoded = re.search(
        r'<script id="payload" type="application/json">(.*?)</script>', page, re.S
    ).group(1)
    assert json.loads(encoded)["title"] == wf.label
    assert "https://cdn" not in page
    assert "__PAYLOAD__" not in page


def test_atomic_output_and_overwrite(tmp_path):
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


def test_io_error_has_cause(tmp_path):
    parent = tmp_path / "file"
    parent.write_text("not a directory")
    with pytest.raises(PluginExecutionError) as caught:
        cwl2webgl.execute(
            context(loaded()), CWL2WebGLOptions(output=parent / "view.html")
        )
    assert isinstance(caught.value.__cause__, OSError)


def test_atomic_failure_cleans_temp(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(PluginExecutionError):
        cwl2webgl.execute(
            context(loaded()),
            CWL2WebGLOptions(output=tmp_path / "view.html", overwrite=True),
        )
    assert not list(tmp_path.iterdir())


def test_real_cwl_loader_normalization(tmp_path):
    loader = pytest.importorskip("cwl_loader")
    path = tmp_path / "example.cwl"
    path.write_text(json.dumps(document()))
    processes = loader.load_cwl_from_location(str(path))
    result = root(Projection(context(processes)).build("main"))
    assert len(result["edges"]) == 2
    assert result["edges"][-1]["sourcePort"] == "echo/result"


def test_runtime_cli_entrypoint(tmp_path):
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
