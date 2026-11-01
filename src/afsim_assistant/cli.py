from __future__ import annotations

import argparse
import json
import sys

from .catalog import build_catalog, load_catalog, save_catalog
from .config import Settings
from .mcp_client import McpError, McpStdioClient
from .ollama_client import OllamaClient, OllamaError
from .orchestrator import (
    build_and_validate_prototype,
    plan_requirement,
    prepare_requirement,
    resolve_requirement,
)
from .project_builder import BuildError
from .search import DEFAULT_STATUSES, rebuild_index, search
from .template_registry import PlanningError


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def command_doctor(settings: Settings, _args: argparse.Namespace) -> int:
    diagnostics = settings.diagnostics()
    required = ("projectskill_root", "demos_root", "mcp_root", "mission")
    ok = all(diagnostics[name]["exists"] for name in required)
    _print({"ok": ok, "diagnostics": diagnostics})
    return 0 if ok else 1


def command_ollama(settings: Settings, args: argparse.Namespace) -> int:
    del settings
    client = OllamaClient.from_environment(model=args.model)
    _print(client.health())
    return 0


def command_mcp(settings: Settings, _args: argparse.Namespace) -> int:
    with McpStdioClient(settings) as client:
        tools = client.list_tools()
    _print({"reachable": True, "tools": [item.get("name") for item in tools]})
    return 0


def command_build_index(settings: Settings, _args: argparse.Namespace) -> int:
    catalog = build_catalog(settings)
    catalog_path = save_catalog(settings, catalog)
    index_result = rebuild_index(settings, catalog)
    _print(
        {
            "ok": True,
            "catalog": str(catalog_path),
            "catalog_entries": len(catalog["entries"]),
            "counts_by_status": catalog["counts_by_status"],
            "index": index_result,
        }
    )
    return 0


def command_catalog(settings: Settings, _args: argparse.Namespace) -> int:
    catalog = load_catalog(settings)
    _print(
        {
            "schema_version": catalog["schema_version"],
            "generated_at": catalog["generated_at"],
            "entries": len(catalog["entries"]),
            "counts_by_status": catalog["counts_by_status"],
        }
    )
    return 0


def command_search(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.index_path.is_file():
        _print({"error": "knowledge index does not exist", "hint": "run build-index first"})
        return 2
    statuses = list(DEFAULT_STATUSES)
    if args.include_unverified:
        statuses.append("unverified")
    hits = search(settings, args.query, statuses=statuses, limit=args.limit)
    _print({"query": args.query, "statuses": statuses, "count": len(hits), "hits": hits})
    return 0


def command_prepare(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.index_path.is_file():
        _print({"error": "knowledge index does not exist", "hint": "run build-index first"})
        return 2
    client = OllamaClient.from_environment(model=args.model)
    result = prepare_requirement(
        args.requirement,
        settings=settings,
        client=client,
        include_unverified=args.include_unverified,
        limit=args.limit,
    )
    _print(result)
    return 0


def command_resolve(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.index_path.is_file():
        _print({"error": "knowledge index does not exist", "hint": "run build-index first"})
        return 2
    client = OllamaClient.from_environment(model=args.model)
    result = resolve_requirement(
        args.requirement,
        settings=settings,
        client=client,
        include_unverified=args.include_unverified,
        knowledge_limit=args.knowledge_limit,
        type_limit=args.type_limit,
    )
    _print(result)
    return 0


def command_prototype(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.index_path.is_file():
        _print({"error": "knowledge index does not exist", "hint": "run build-index first"})
        return 2
    client = OllamaClient.from_environment(model=args.model)
    result = build_and_validate_prototype(
        args.requirement,
        settings=settings,
        client=client,
        scenario_id=args.scenario_id,
    )
    _print(result)
    return 0 if result["build"]["validation"].get("ok") else 3


def command_plan(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.index_path.is_file():
        _print({"error": "knowledge index does not exist", "hint": "run build-index first"})
        return 2
    client = OllamaClient.from_environment(model=args.model)
    result = plan_requirement(
        args.requirement,
        settings=settings,
        client=client,
        include_unverified=False,
        knowledge_limit=args.knowledge_limit,
        type_limit=args.type_limit,
    )
    _print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="afsim-assistant")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("doctor", help="check local AFSIM assistant paths")
    ollama_parser = subcommands.add_parser("ollama", help="check Ollama and the selected model")
    ollama_parser.add_argument("--model")
    subcommands.add_parser("mcp", help="check the local AFSIM MCP server")
    subcommands.add_parser("build-index", help="build catalog.json and SQLite FTS5 index")
    subcommands.add_parser("catalog", help="show catalog statistics")

    search_parser = subcommands.add_parser("search", help="search verified and official knowledge")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.add_argument("--include-unverified", action="store_true")

    prepare_parser = subcommands.add_parser(
        "prepare", help="parse a natural-language requirement and retrieve knowledge"
    )
    prepare_parser.add_argument("requirement")
    prepare_parser.add_argument("--model")
    prepare_parser.add_argument("--limit", type=int, default=8)
    prepare_parser.add_argument("--include-unverified", action="store_true")

    resolve_parser = subcommands.add_parser(
        "resolve", help="parse a requirement, retrieve knowledge and rank real AFSIM types"
    )
    resolve_parser.add_argument("requirement")
    resolve_parser.add_argument("--model")
    resolve_parser.add_argument("--knowledge-limit", type=int, default=8)
    resolve_parser.add_argument("--type-limit", type=int, default=5)
    resolve_parser.add_argument("--include-unverified", action="store_true")

    plan_parser = subcommands.add_parser(
        "plan", help="select a verified template context and bind its local AFSIM types"
    )
    plan_parser.add_argument("requirement")
    plan_parser.add_argument("--model")
    plan_parser.add_argument("--knowledge-limit", type=int, default=8)
    plan_parser.add_argument("--type-limit", type=int, default=5)

    prototype_parser = subcommands.add_parser(
        "prototype", help="build and validate the supported SAM-vs-aircraft prototype"
    )
    prototype_parser.add_argument("requirement")
    prototype_parser.add_argument("--model")
    prototype_parser.add_argument("--scenario-id")
    return parser


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.discover()
    handlers = {
        "doctor": command_doctor,
        "ollama": command_ollama,
        "mcp": command_mcp,
        "build-index": command_build_index,
        "catalog": command_catalog,
        "search": command_search,
        "prepare": command_prepare,
        "resolve": command_resolve,
        "plan": command_plan,
        "prototype": command_prototype,
    }
    try:
        code = handlers[args.command](settings, args)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        OllamaError,
        McpError,
        BuildError,
        PlanningError,
    ) as exc:
        _print({"error": str(exc), "command": args.command})
        code = 1
    raise SystemExit(code)

