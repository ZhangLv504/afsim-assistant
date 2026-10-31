from __future__ import annotations

import re


SCENARIO_SPEC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scenario_name": {"type": "string"},
        "summary": {"type": "string"},
        "duration": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "value": {"type": "number"},
                "unit": {
                    "type": "string",
                    "enum": ["seconds", "minutes", "hours"],
                },
            },
            "required": ["value", "unit"],
        },
        "forces": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "side": {"type": "string", "enum": ["blue", "red", "neutral"]},
                    "role": {
                        "type": "string",
                        "enum": [
                            "air_defense_site",
                            "aircraft",
                            "ground_vehicle",
                            "ship",
                            "submarine",
                            "missile",
                            "radar_site",
                            "command_post",
                            "other",
                        ],
                    },
                    "domain": {
                        "type": "string",
                        "enum": ["air", "land", "surface", "subsurface", "space", "unknown"],
                    },
                    "count": {"type": "integer", "minimum": 1},
                    "requested_type": {"type": ["string", "null"]},
                },
                "required": ["side", "role", "domain", "count", "requested_type"],
            },
        },
        "capabilities": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "detection",
                    "tracking",
                    "weapon_engagement",
                    "communications",
                    "movement",
                    "visualization",
                    "analysis",
                ],
            },
        },
        "constraints": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "search_terms": {
            "type": "array",
            "minItems": 2,
            "maxItems": 8,
            "items": {"type": "string"},
        },
    },
    "required": [
        "scenario_name",
        "summary",
        "duration",
        "forces",
        "capabilities",
        "constraints",
        "unknowns",
        "search_terms",
    ],
}


SYSTEM_PROMPT = """你是 AFSIM 场景需求解析器，不是脚本生成器。
把用户需求整理成给后续确定性编排器使用的 ScenarioSpec JSON。

规则：
1. 不得编造具体 AFSIM platform_type、sensor、weapon 或 processor 名称。
2. 用户没有明确指定的内容写入 unknowns，不要自行补全战术参数。
3. requested_type 仅用于用户原文明确给出的 AFSIM 标识符，例如 LTE_FIGHTER；
   “地空导弹阵地”“飞机”“雷达”等普通角色必须填 null。
4. search_terms 必须使用适合检索 AFSIM 官方英文 Demo 的简短英文词组，
   例如 "SAM launcher"、"radar sensor"、"air target"、"weapon processor"。
5. capabilities 只能表示用户明确要求的能力。雷达探测=detection，
   跟踪=tracking，导弹攻击/拦截=weapon_engagement。
6. constraints 只能记录用户原文提出的限制，不得写入系统内部规则。
7. 地空导弹阵地 role=air_defense_site；飞机 role=aircraft；舰艇 role=ship。
8. duration 已单独记录，不得再把仿真时长重复写入 constraints。
9. scenario_name 使用简短 snake_case 英文名称。
10. 只返回符合给定 JSON Schema 的对象。
"""


ROLE_DOMAINS = {
    "air_defense_site": "land",
    "aircraft": "air",
    "ground_vehicle": "land",
    "ship": "surface",
    "submarine": "subsurface",
    "radar_site": "land",
    "command_post": "land",
}


def validate_spec(spec: dict) -> dict:
    required = tuple(SCENARIO_SPEC_SCHEMA["required"])
    missing = [key for key in required if key not in spec]
    if missing:
        raise ValueError(f"ScenarioSpec missing fields: {', '.join(missing)}")
    if not isinstance(spec.get("forces"), list):
        raise ValueError("ScenarioSpec.forces must be an array")
    for force in spec["forces"]:
        expected_domain = ROLE_DOMAINS.get(force.get("role"))
        if expected_domain:
            force["domain"] = expected_domain
        requested = force.get("requested_type")
        if requested is not None:
            text = str(requested).strip()
            # AFSIM type identifiers are conventionally uppercase symbolic
            # names. Generic role phrases from the model are not closed-
            # namespace types and must be resolved later through afsim_types.
            if not re.fullmatch(r"[A-Z][A-Z0-9_-]+", text):
                force["requested_type"] = None
    terms = spec.get("search_terms")
    if not isinstance(terms, list) or not 2 <= len(terms) <= 8:
        raise ValueError("ScenarioSpec.search_terms must contain 2-8 terms")
    cleaned = []
    for term in terms:
        text = re.sub(r"\s+", " ", str(term)).strip()
        if text and text.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(text)
    if len(cleaned) < 2:
        raise ValueError("ScenarioSpec.search_terms must contain at least 2 distinct terms")
    spec["search_terms"] = cleaned[:8]
    spec["capabilities"] = list(dict.fromkeys(spec.get("capabilities") or []))
    if spec.get("duration") is not None:
        duration_words = re.compile(
            r"\b(simulat(?:e|ion)|duration|seconds?|minutes?|hours?)\b",
            flags=re.IGNORECASE,
        )
        spec["constraints"] = [
            item
            for item in (spec.get("constraints") or [])
            if not duration_words.search(str(item))
        ]
    return spec

