"""Regression fixture: original EOAP Pattern 12 and pinned imported schema bytes."""

import json
from pathlib import Path

from cwl_utils.parser import load_document_by_uri
from cwl_utils.parser.cwl_v1_2 import LoadingOptions
from schema_salad.fetcher import DefaultFetcher
from transpiler_mate.api import SoftwareApplication, TranspilerContext

from cwl2webgl.plugin import CWL2WebGLOptions, cwl2webgl
from cwl2webgl.projection import Projection

ROOT = Path(__file__).resolve().parent.parent


class NoResolver:
    def resolve(self, location):
        raise AssertionError(f"Unexpected external process: {location}")


def pattern_context():
    cache = {
        "https://raw.githubusercontent.com/eoap/schemas/main/" + name: (
            ROOT / "tests" / "fixtures" / name
        ).read_text()
        for name in ("ogc.yaml", "string_format.yaml")
    }
    source = (ROOT / "tests" / "fixtures" / "pattern-12.cwl").as_uri()
    dom = load_document_by_uri(
        source,
        load_all=True,
        loadingOptions=LoadingOptions(
            fetcher=DefaultFetcher(cache, None), no_link_check=True
        ),
    )
    # Supply the display name consumed by the plugin; the fixture does not
    # supply all SoftwareApplication fields required by the runtime.
    return TranspilerContext(
        source=source,
        document={p.id: p for p in dom},
        process_id="pattern-12",
        metadata=SoftwareApplication.model_construct(name="Pattern 12"),
        resolver=NoResolver(),
    )


def test_pattern12_structure_and_named_schemas(tmp_path):
    ctx = pattern_context()
    before = [p.save() for p in ctx.processes]
    payload = Projection(ctx).build("pattern-12")
    view = payload["views"][payload["roots"][0]]
    assert len(view["nodes"]) == 12
    assert len(view["edges"]) == 14  # Includes aoi -> aoi AND aoi -> epsg.
    assert sum(n["kind"] == "input" for n in view["nodes"]) == 6
    assert sum(n["kind"] == "output" for n in view["nodes"]) == 3
    crop = next(n for n in view["nodes"] if n["cwlId"].endswith("/node_crop"))
    assert crop["details"]["scatterMethod"] == "dotproduct"
    assert crop["details"]["scatter"].endswith("/band")
    assert len(crop["details"]["inputs"]) == 5
    assert "ogc.yaml#BBox" in json.dumps(crop["details"])
    cwl2webgl.execute(ctx, CWL2WebGLOptions(output=tmp_path / "pattern-12.html"))
    assert [p.save() for p in ctx.processes] == before


if __name__ == "__main__":
    cwl2webgl.execute(
        pattern_context(),
        CWL2WebGLOptions(output=ROOT / "examples" / "pattern-12.html", overwrite=True),
    )
