"""Read cwl-utils objects directly; emit only browser presentation data.

There is intentionally no second CWL model, parser, or graph library here.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urldefrag, urljoin

from cwl_utils.parser import Workflow
from transpiler_mate.api import (
    PluginExecutionError,
    PluginFailureError,
    TranspilerContext,
)


def many(value: Any) -> list[Any]:
    return [] if value is None else value if isinstance(value, list) else [value]


def short(value: str) -> str:
    return value.rsplit("#", 1)[-1].rstrip("/").rsplit("/", 1)[-1]


def node_id(kind: str, identifier: str) -> str:
    # Normalized DOMs can use the same local name for an input, step and output.
    return json.dumps([kind, identifier], separators=(",", ":"))


def plain(value: Any) -> Any:
    """Use the DOM's serializer for schemas, bindings, requirements and extensions."""
    if hasattr(value, "save"):
        return value.save(top=False, relative_uris=False)
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    return value


def details(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        name.rstrip("_"): plain(getattr(obj, name))
        for name in fields
        if getattr(obj, name, None) is not None
    }


PORT_FIELDS = (
    "id",
    "label",
    "doc",
    "type_",
    "default",
    "format",
    "secondaryFiles",
    "streamable",
    "inputBinding",
    "outputBinding",
    "loadContents",
    "loadListing",
)
STEP_FIELDS = (
    "id",
    "label",
    "doc",
    "when",
    "scatter",
    "scatterMethod",
    "requirements",
    "hints",
)
BINDING_FIELDS = (
    "id",
    "source",
    "default",
    "valueFrom",
    "linkMerge",
    "pickValue",
    "loadContents",
    "loadListing",
)


def find_process(context: TranspilerContext, reference: str) -> Any | None:
    """Match exact IDs, or document-scoped fragment aliases. Never match basenames."""
    base, fragment = urldefrag(reference)
    source_base = urldefrag(str(context.source))[0]
    aliases = {reference}
    if fragment and (not base or base == source_base):
        aliases.update((fragment, "#" + fragment))
    matches = {
        id(process): process
        for key, process in context.document.items()
        if key in aliases or process.id in aliases
    }
    if len(matches) > 1:
        raise PluginFailureError(f"Ambiguous process reference: {reference}")
    return next(iter(matches.values()), None)


class Projection:
    """Per-invocation traversal state, containing references to the existing DOM."""

    def __init__(self, context: TranspilerContext):
        self.context = context
        self.views: dict[str, dict[str, Any]] = {}
        self.resolved: dict[str, TranspilerContext] = {}
        self.active: set[str] = set()

    def run(
        self, step: Any, context: TranspilerContext
    ) -> tuple[Any, TranspilerContext]:
        if not isinstance(step.run, str):
            return step.run, context
        process = find_process(context, step.run)
        if process is not None:
            return process, context
        # cwl-utils normally supplies absolute URIs; normalized DOMs may retain fragments.
        location = urljoin(str(context.source), step.run)
        process = find_process(context, location)
        if process is not None:
            return process, context
        if location not in self.resolved:
            try:
                self.resolved[location] = context.resolver.resolve(location)
            except Exception as exc:
                raise PluginExecutionError(
                    f"Cannot resolve run {step.run!r} for {step.id}"
                ) from exc
        other = self.resolved[location]
        process = find_process(other, location)
        if process is None and other.process_id:
            process = find_process(other, other.process_id)
        if process is None and not urldefrag(location)[1] and len(other.document) == 1:
            process = next(iter(other.processes))
        if process is None:
            raise PluginFailureError(
                f"Resolved source does not identify run {location!r}"
            )
        return process, other

    def view(self, workflow: Any, context: TranspilerContext) -> str:
        key = str(context.source) + "|" + workflow.id
        if key in self.active:
            raise PluginFailureError(f"Recursive workflow reference: {workflow.id}")
        if key in self.views:
            return key
        self.active.add(key)
        sources: dict[str, tuple[str, str]] = {}
        nodes = self._nodes(workflow, context, sources)
        edges = self._edges(workflow, sources)
        self.views[key] = {
            "id": workflow.id,
            "label": workflow.label or short(workflow.id),
            "details": details(
                workflow, ("id", "label", "doc", "requirements", "hints")
            ),
            "nodes": nodes,
            "edges": edges,
        }
        self.active.remove(key)
        return key

    def _nodes(
        self,
        workflow: Any,
        context: TranspilerContext,
        sources: dict[str, tuple[str, str]],
    ) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []

        def node(
            identifier: str, kind: str, obj: Any, info: dict[str, Any]
        ) -> dict[str, Any]:
            result = {
                "id": node_id("step" if kind == "workflow" else kind, identifier),
                "cwlId": identifier,
                "kind": kind,
                "label": getattr(obj, "label", None) or short(identifier),
                "details": info,
            }
            if any(n["id"] == result["id"] for n in nodes):
                raise PluginFailureError(f"Duplicate node ID: {identifier}")
            nodes.append(result)
            return result

        for port in workflow.inputs:
            node(port.id, "input", port, details(port, PORT_FIELDS))
            sources[port.id] = (node_id("input", port.id), port.id)
        for step in workflow.steps:
            process, owner = self.run(step, context)
            info = details(step, STEP_FIELDS)
            info["run"] = process.id
            info["bindings"] = [details(port, BINDING_FIELDS) for port in step.in_]
            info["inputs"] = [details(port, PORT_FIELDS) for port in process.inputs]
            info["outputs"] = [details(port, PORT_FIELDS) for port in process.outputs]
            info["process"] = details(
                process,
                (
                    "class_",
                    "label",
                    "doc",
                    "requirements",
                    "hints",
                    "baseCommand",
                    "arguments",
                    "expression",
                ),
            )
            result = node(
                step.id,
                "workflow" if isinstance(process, Workflow) else "step",
                step,
                info,
            )
            if isinstance(process, Workflow):
                result["child"] = self.view(process, owner)
            for output in step.out:
                identifier = output if isinstance(output, str) else output.id
                # cwl-loader's normalized DOM has out=["result"], source="step/result".
                if "/" not in identifier and "#" not in identifier:
                    identifier = step.id + "/" + identifier
                if identifier in sources:
                    raise PluginFailureError(f"Duplicate source port: {identifier}")
                sources[identifier] = (node_id("step", step.id), identifier)
        for port in workflow.outputs:
            node(
                port.id,
                "output",
                port,
                details(port, PORT_FIELDS + ("outputSource", "linkMerge", "pickValue")),
            )

        return nodes

    def _edges(
        self, workflow: Any, sources: dict[str, tuple[str, str]]
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []

        def connect(
            reference: str, target: str, port: str, binding: dict[str, Any]
        ) -> None:
            if reference not in sources:
                raise PluginFailureError(
                    f"Unknown source {reference!r} in workflow {workflow.id}"
                )
            source, source_port = sources[reference]
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "sourcePort": source_port,
                    "targetPort": port,
                    "binding": binding,
                }
            )

        for step in workflow.steps:
            for port in step.in_:
                for reference in many(port.source):
                    connect(
                        reference,
                        node_id("step", step.id),
                        port.id,
                        details(port, BINDING_FIELDS),
                    )
        for port in workflow.outputs:
            for reference in many(port.outputSource):
                connect(
                    reference,
                    node_id("output", port.id),
                    port.id,
                    details(port, ("linkMerge", "pickValue")),
                )
        return edges

    def build(self, workflow_id: str | None = None) -> dict[str, Any]:
        requested = workflow_id or self.context.process_id
        if requested:
            selected = find_process(self.context, requested)
            if selected is None:
                # Convenient short selection is allowed only when unique, never for run resolution.
                matches = [
                    p
                    for p in self.context.processes
                    if short(p.id) == requested.lstrip("#")
                ]
                selected = matches[0] if len(matches) == 1 else None
            if selected is None or not isinstance(selected, Workflow):
                raise PluginFailureError(
                    f"Select an existing Workflow ID; got {requested!r}"
                )
            workflows = [selected]
        else:
            workflows = [
                process
                for process in self.context.processes
                if isinstance(process, Workflow)
            ]
        if not workflows:
            raise PluginFailureError("The source contains no Workflow processes")
        roots = [self.view(workflow, self.context) for workflow in workflows]
        return {"version": 1, "roots": roots, "views": self.views}
