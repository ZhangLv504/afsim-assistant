from __future__ import annotations

from typing import Protocol


class ToolCaller(Protocol):
    def call_tool(self, name: str, arguments: dict | None = None) -> dict: ...


ROLE_QUERIES = {
    "air_defense_site": ("SAM",),
    "aircraft": ("AIR_TARGET", "FIGHTER"),
    "ground_vehicle": ("VEHICLE", "TANK"),
    "ship": ("SHIP",),
    "submarine": ("SUBMARINE",),
    "missile": ("MISSILE",),
    "radar_site": ("RADAR",),
    "command_post": ("COMMAND",),
    "other": (),
}


DOMAIN_MAP = {
    "air": "air",
    "land": "ground",
    "surface": "surface",
    "subsurface": "subsurface",
    "space": "space",
}


def _score_candidate(candidate: dict, force: dict) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    upper_name = str(candidate.get("name") or "").upper()
    role = force.get("role")
    domain = force.get("domain")

    expected = DOMAIN_MAP.get(domain)
    actual = candidate.get("domain")
    if actual == expected:
        score += 3.0
        reasons.append(f"domain={actual}")
    elif actual == "undetermined" and role in {"air_defense_site", "radar_site", "command_post"}:
        score += 1.0
        reasons.append("fixed-site domain may be undetermined")

    role_tokens = {
        "air_defense_site": ("SAM",),
        "aircraft": ("AIR_TARGET", "FIGHTER", "AIRPLANE"),
        "ground_vehicle": ("VEHICLE", "TANK"),
        "ship": ("SHIP", "DESTROYER", "FRIGATE"),
        "submarine": ("SUB",),
        "missile": ("MISSILE", "MSL"),
        "radar_site": ("RADAR",),
        "command_post": ("COMMAND", "C2"),
    }.get(role, ())
    if any(token in upper_name for token in role_tokens):
        score += 3.0
        reasons.append("name matches role")
    if role == "aircraft" and upper_name == "AIR_TARGET":
        score += 5.0
        reasons.append("exact generic air-target type")

    sensors = int(candidate.get("sensors") or 0)
    weapons = int(candidate.get("weapons") or 0)
    processors = int(candidate.get("processors") or 0)
    defined_in = str(candidate.get("defined_in") or "").replace("\\", "/").lower()
    if role == "air_defense_site":
        if "/weapons/" in f"/{defined_in}":
            score -= 12.0
            reasons.append("penalty: definition is a launched weapon platform")
        if sensors > 0:
            score += 2.0
            reasons.append("has sensor")
        if weapons > 0:
            score += 3.0
            reasons.append("has weapon")
        if processors > 0:
            score += 1.0
            reasons.append("has processor")
        if candidate.get("can_engage"):
            score += 3.0
            reasons.append("can_engage")
    elif role == "aircraft":
        if "/weapons/" in f"/{defined_in}":
            score -= 12.0
            reasons.append("penalty: definition is a weapon, not an aircraft role")
        if weapons == 0:
            score += 2.0
            reasons.append("unarmed target")
        if candidate.get("loads"):
            score += 1.0
            reasons.append("known to load in demos")

    if candidate.get("defining_file_instantiates"):
        score += 0.5
        reasons.append("demo contains instances")
    return score, reasons


def _list_candidates(caller: ToolCaller, force: dict, limit: int) -> list[dict]:
    requested = force.get("requested_type")
    if requested:
        exact = caller.call_tool("afsim_types", {"name": requested})
        return [
            {
                "name": exact.get("name", requested),
                "score": 100.0,
                "reasons": ["explicit user-supplied AFSIM type"],
                "facts": exact,
            }
        ]

    candidates: dict[str, dict] = {}
    for keyword in ROLE_QUERIES.get(force.get("role"), ()):
        arguments = {"keyword": keyword, "limit": max(30, limit * 6)}
        # Movers make these domains trustworthy. Fixed sites are deliberately
        # left unfiltered because the MCP correctly reports many of them as
        # undetermined when no mover exists in their base chain.
        if force.get("role") not in {"air_defense_site", "radar_site", "command_post"}:
            domain = DOMAIN_MAP.get(force.get("domain"))
            if domain:
                arguments["domain"] = domain
        payload = caller.call_tool(
            "afsim_types",
            arguments,
        )
        for item in payload.get("types") or []:
            candidates.setdefault(str(item.get("name")), item)

    ranked = []
    for item in candidates.values():
        score, reasons = _score_candidate(item, force)
        ranked.append(
            {
                "name": item.get("name"),
                "score": score,
                "reasons": reasons,
                "facts": item,
            }
        )
    ranked.sort(key=lambda item: (-item["score"], str(item["name"]).upper()))
    return ranked[:limit]


def resolve_force_types(caller: ToolCaller, spec: dict, *, limit: int = 5) -> list[dict]:
    resolved = []
    for index, force in enumerate(spec.get("forces") or []):
        resolved.append(
            {
                "force_index": index,
                "force": force,
                "candidates": _list_candidates(caller, force, limit),
            }
        )
    return resolved

