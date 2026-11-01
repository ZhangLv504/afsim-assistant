from __future__ import annotations


class PlanningError(RuntimeError):
    pass


TEMPLATE_PROFILES = (
    {
        "id": "official.launcher.sam_air_intercept",
        "source_relative": "launcher",
        "entry_reference": "1st_run.txt",
        "required_roles": {
            "air_defense_site": 1,
            "aircraft": 1,
        },
        "required_capabilities": {
            "detection",
            "tracking",
            "weapon_engagement",
        },
        "context_types": {
            "air_defense_site": "SAM_LAUNCHER",
            "aircraft": "AIRPLANE",
        },
        "dependency_strategy": "copy_official_demo_subtree",
    },
)


def _role_counts(spec: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for force in spec.get("forces") or []:
        role = str(force.get("role") or "")
        counts[role] = counts.get(role, 0) + int(force.get("count") or 0)
    return counts


def _resolution_by_force(type_resolution: list[dict] | None) -> dict[int, dict]:
    return {
        int(item["force_index"]): item
        for item in (type_resolution or [])
        if item.get("force_index") is not None
    }


def _profile_problems(profile: dict, spec: dict) -> list[str]:
    problems = []
    actual_roles = _role_counts(spec)
    if actual_roles != profile["required_roles"]:
        problems.append(
            f"roles/counts {actual_roles!r} do not match {profile['required_roles']!r}"
        )

    missing = profile["required_capabilities"] - set(spec.get("capabilities") or [])
    if missing:
        problems.append("missing capabilities: " + ", ".join(sorted(missing)))

    for force in spec.get("forces") or []:
        selected = profile["context_types"].get(force.get("role"))
        requested = force.get("requested_type")
        if requested and selected and str(requested).upper() != selected.upper():
            problems.append(
                f"requested type {requested} is not available as role {force.get('role')} "
                f"in this template context (expected {selected})"
            )
    return problems


def select_generation_plan(
    spec: dict,
    type_resolution: list[dict] | None = None,
) -> dict:
    evaluated = []
    compatible = []
    for profile in TEMPLATE_PROFILES:
        problems = _profile_problems(profile, spec)
        evaluated.append({"template_id": profile["id"], "problems": problems})
        if not problems:
            compatible.append(profile)

    if not compatible:
        detail = "; ".join(
            f"{item['template_id']}: {', '.join(item['problems'])}"
            for item in evaluated
        )
        raise PlanningError(f"no compatible verified template: {detail}")

    profile = sorted(compatible, key=lambda item: item["id"])[0]
    resolved = _resolution_by_force(type_resolution)
    bindings = []
    for index, force in enumerate(spec.get("forces") or []):
        role = force["role"]
        selected = profile["context_types"][role]
        global_candidates = [
            item.get("name")
            for item in (resolved.get(index, {}).get("candidates") or [])
            if item.get("name")
        ]
        bindings.append(
            {
                "force_index": index,
                "side": force.get("side"),
                "role": role,
                "selected_type": selected,
                "selection_source": "verified_template_context",
                "requested_type": force.get("requested_type"),
                "global_candidates_for_reference": global_candidates,
            }
        )

    return {
        "schema_version": 1,
        "template": {
            "id": profile["id"],
            "source_relative": profile["source_relative"],
            "entry_reference": profile["entry_reference"],
            "dependency_strategy": profile["dependency_strategy"],
        },
        "force_bindings": bindings,
        "selection_policy": {
            "global_candidates_are_advisory": True,
            "types_must_come_from_selected_template_context": True,
            "unverified_cross_demo_dependency_copying": False,
        },
        "evaluated_templates": evaluated,
    }
