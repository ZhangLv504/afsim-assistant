from __future__ import annotations

from pathlib import Path

from .config import Settings
from .mcp_client import McpStdioClient
from .ollama_client import OllamaClient
from .project_builder import (
    build_sam_air_intercept,
    enforce_capability_evidence,
    record_validation,
)
from .scenario_spec import SCENARIO_SPEC_SCHEMA, SYSTEM_PROMPT, validate_spec
from .search import DEFAULT_STATUSES, search
from .template_registry import select_generation_plan
from .type_resolver import resolve_force_types


def parse_requirement(requirement: str, client: OllamaClient) -> dict:
    text = str(requirement or "").strip()
    if not text:
        raise ValueError("requirement must be non-empty")
    spec = client.structured_chat(
        system=SYSTEM_PROMPT,
        user=text,
        schema=SCENARIO_SPEC_SCHEMA,
    )
    return validate_spec(spec)


def retrieve_for_spec(
    settings: Settings,
    spec: dict,
    *,
    include_unverified: bool = False,
    limit: int = 8,
) -> list[dict]:
    statuses = list(DEFAULT_STATUSES)
    if include_unverified:
        statuses.append("unverified")

    # Reciprocal-rank fusion prevents one broad term from monopolising all
    # results while keeping retrieval deterministic and inexpensive.
    combined: dict[str, dict] = {}
    for term in spec["search_terms"]:
        for rank, hit in enumerate(search(settings, term, statuses=statuses, limit=6), start=1):
            doc_id = hit["doc_id"]
            item = combined.setdefault(doc_id, {**hit, "matched_terms": [], "retrieval_score": 0.0})
            item["matched_terms"].append(term)
            item["retrieval_score"] += 1.0 / (60.0 + rank)

    ranked = sorted(
        combined.values(),
        key=lambda item: (-item["retrieval_score"], item["status"], item["doc_id"]),
    )
    return ranked[: max(1, min(int(limit), 20))]


def prepare_requirement(
    requirement: str,
    *,
    settings: Settings,
    client: OllamaClient,
    include_unverified: bool = False,
    limit: int = 8,
) -> dict:
    spec = parse_requirement(requirement, client)
    hits = retrieve_for_spec(
        settings,
        spec,
        include_unverified=include_unverified,
        limit=limit,
    )
    return {
        "requirement": requirement,
        "model": client.model,
        "scenario_spec": spec,
        "knowledge": {
            "include_unverified": include_unverified,
            "count": len(hits),
            "hits": hits,
        },
    }


def resolve_requirement(
    requirement: str,
    *,
    settings: Settings,
    client: OllamaClient,
    include_unverified: bool = False,
    knowledge_limit: int = 8,
    type_limit: int = 5,
) -> dict:
    prepared = prepare_requirement(
        requirement,
        settings=settings,
        client=client,
        include_unverified=include_unverified,
        limit=knowledge_limit,
    )
    with McpStdioClient(settings) as mcp:
        prepared["type_resolution"] = resolve_force_types(
            mcp,
            prepared["scenario_spec"],
            limit=type_limit,
        )
    return prepared


def plan_requirement(
    requirement: str,
    *,
    settings: Settings,
    client: OllamaClient,
    include_unverified: bool = False,
    knowledge_limit: int = 8,
    type_limit: int = 5,
) -> dict:
    resolved = resolve_requirement(
        requirement,
        settings=settings,
        client=client,
        include_unverified=include_unverified,
        knowledge_limit=knowledge_limit,
        type_limit=type_limit,
    )
    resolved["generation_plan"] = select_generation_plan(
        resolved["scenario_spec"],
        resolved["type_resolution"],
    )
    return resolved


def build_and_validate_prototype(
    requirement: str,
    *,
    settings: Settings,
    client: OllamaClient,
    scenario_id: str | None = None,
) -> dict:
    resolved = plan_requirement(
        requirement,
        settings=settings,
        client=client,
        include_unverified=False,
        knowledge_limit=6,
        type_limit=5,
    )
    build = build_sam_air_intercept(
        settings,
        resolved["scenario_spec"],
        scenario_id=scenario_id,
        generation_plan=resolved["generation_plan"],
    )
    with McpStdioClient(settings) as mcp:
        raw_validation = mcp.call_tool(
            "run_mission",
            {
                "scenario": build["entry_file"],
                "working_dir": build["project_dir"],
                "output_dir": str(Path(build["project_dir"]) / "output"),
                "timeout_sec": 300,
                "include_stdout": True,
                "stdout_chars": 12000,
            },
        )
    validation = enforce_capability_evidence(resolved["scenario_spec"], raw_validation)
    completed = record_validation(build, validation)
    return {
        "requirement": requirement,
        "scenario_spec": resolved["scenario_spec"],
        "type_resolution": resolved["type_resolution"],
        "generation_plan": resolved["generation_plan"],
        "build": completed,
    }

