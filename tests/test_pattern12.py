"""Regression fixture: original EOAP Pattern 12 and pinned imported schema bytes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from cwl_utils.parser import LoadingOptions, load_document_by_uri
from pydantic import AnyUrl
from schema_salad.fetcher import DefaultFetcher
from transpiler_mate.api import SoftwareApplication, TranspilerContext

from cwl2webgl.plugin import CWL2WebGLOptions, cwl2webgl
from cwl2webgl.projection import Projection

if TYPE_CHECKING:
    from rdflib import Graph

ROOT = Path(__file__).resolve().parent.parent


class NoResolver:
    """Reject unexpected external process resolution."""

    def resolve(self, location: str) -> TranspilerContext:
        """Fail if the fixture attempts external process resolution."""
        raise AssertionError(f"Unexpected external process: {location}")


def pattern_context() -> TranspilerContext:
    """Load Pattern 12 using pinned schema documents."""
    cache: dict[str, str | Graph | bool] = {
        "https://raw.githubusercontent.com/eoap/schemas/main/" + name: (
            ROOT / "tests" / "fixtures" / name
        ).read_text()
        for name in ("ogc.yaml", "string_format.yaml")
    }
    source = (ROOT / "tests" / "fixtures" / "pattern-12.cwl").as_uri()
    dom = load_document_by_uri(
        source,
        load_all=True,
        loadingOptions=LoadingOptions(fetcher=DefaultFetcher(cache, None), no_link_check=True),
    )
    # Supply the display name consumed by the plugin; the fixture does not
    # supply all SoftwareApplication fields required by the runtime.
    return TranspilerContext(
        source=AnyUrl(source),
        document={p.id: p for p in dom},
        process_id="pattern-12",
        metadata=SoftwareApplication.model_construct(name="Pattern 12"),
        resolver=NoResolver(),
    )


def test_pattern12_structure_and_named_schemas(tmp_path: Path) -> None:
    ctx = pattern_context()
    before = [p.save() for p in ctx.processes]
    payload = Projection(ctx).build("pattern-12")
    view = payload["views"][payload["roots"][0]]
    expected_nodes = 12
    assert len(view["nodes"]) == expected_nodes
    expected_edges = 14
    assert len(view["edges"]) == expected_edges  # Includes aoi -> aoi AND aoi -> epsg.
    expected_inputs = 6
    assert sum(n["kind"] == "input" for n in view["nodes"]) == expected_inputs
    expected_outputs = 3
    assert sum(n["kind"] == "output" for n in view["nodes"]) == expected_outputs
    crop = next(n for n in view["nodes"] if n["cwlId"].endswith("/node_crop"))
    assert crop["details"]["scatterMethod"] == "dotproduct"
    assert crop["details"]["scatter"].endswith("/band")
    expected_crop_inputs = 5
    assert len(crop["details"]["inputs"]) == expected_crop_inputs
    assert "ogc.yaml#BBox" in json.dumps(crop["details"])
    cwl2webgl.execute(ctx, CWL2WebGLOptions(output=tmp_path / "pattern-12.html"))
    assert [p.save() for p in ctx.processes] == before


if __name__ == "__main__":
    cwl2webgl.execute(
        pattern_context(),
        CWL2WebGLOptions(output=ROOT / "examples" / "pattern-12.html", overwrite=True),
    )
