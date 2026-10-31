from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import Settings


TEXT_EXTENSIONS = {".txt", ".md"}

# These files were exercised together with AFSIM 2.9 mission.exe on
# 2026-10-31. The run completed, fired MSL_1, and wrote AER/EVT/LOG outputs.
VALIDATED_MINIMAL_FILES = {
    "event_output.txt",
    "main.txt",
    "platforms/building.txt",
    "platforms/tank.txt",
    "processors/missile_processor.txt",
    "scenarios/blue_laydown.txt",
    "scenarios/red_laydown.txt",
    "setup.txt",
    "weapons/missile.txt",
}

DEMO_EXCLUDED_PARTS = {
    "data",
    "output",
    "outputs",
    "result",
    "results",
    "expected_results",
    "satcat",
}

DEMO_EXCLUDED_NAME_FRAGMENTS = (
    "_data.txt",
    "launch_data",
    "lookup_table",
)

PROJECTSKILL_NAVIGATION_FILES = {"INDEX.md"}


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    source: str
    category: str
    status: str
    path: str
    relative_path: str
    title: str
    tags: list[str]
    size_bytes: int
    exclusion_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _title(path: Path) -> str:
    # AFSIM .txt files often start with classification/license banners (for
    # example "CUI"), which are poor result titles. Their file names carry the
    # useful domain name more reliably.
    if path.suffix.lower() == ".txt":
        return path.stem.replace("_", " ")
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _ in range(40):
                line = handle.readline()
                if not line:
                    break
                text = line.strip().lstrip("#").strip()
                if text and not set(text) <= {"=", "-", "*", "/"}:
                    return text[:160]
    except OSError:
        pass
    return path.stem.replace("_", " ")


def _tags(relative: Path) -> list[str]:
    tokens: list[str] = []
    for part in relative.with_suffix("").parts:
        tokens.extend(re.split(r"[^A-Za-z0-9_]+", part.lower()))
    return sorted({token for token in tokens if token})


def _is_projectskill_leo(relative: Path) -> bool:
    normalized = relative.as_posix().lower()
    return "leo" in normalized


def iter_projectskill(settings: Settings) -> Iterable[CatalogEntry]:
    root = settings.projectskill_root
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        relative = path.relative_to(root)
        rel_text = relative.as_posix()
        excluded = _is_projectskill_leo(relative)
        if excluded:
            status = "excluded"
            reason = "LEO resources may depend on custom AFSIM types/extensions"
        elif rel_text in PROJECTSKILL_NAVIGATION_FILES:
            status = "excluded"
            reason = "navigation metadata is not generation knowledge"
        elif rel_text.startswith("templates/") and rel_text.removeprefix("templates/") in VALIDATED_MINIMAL_FILES:
            status = "validated"
            reason = None
        else:
            status = "unverified"
            reason = None
        category = relative.parts[0] if len(relative.parts) > 1 else "skill"
        yield CatalogEntry(
            id=f"projectskill:{rel_text}",
            source="projectskill",
            category=category,
            status=status,
            path=str(path.resolve()),
            relative_path=rel_text,
            title=_title(path),
            tags=_tags(relative),
            size_bytes=path.stat().st_size,
            exclusion_reason=reason,
        )


def _demo_allowed(path: Path, root: Path, max_bytes: int) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    try:
        if path.stat().st_size > max_bytes:
            return False
    except OSError:
        return False
    relative = path.relative_to(root)
    lowered_parts = {part.lower() for part in relative.parts[:-1]}
    if lowered_parts & DEMO_EXCLUDED_PARTS:
        return False
    name = relative.name.lower()
    return not any(fragment in name for fragment in DEMO_EXCLUDED_NAME_FRAGMENTS)


def iter_demos(settings: Settings) -> Iterable[CatalogEntry]:
    root = settings.demos_root
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _demo_allowed(path, root, settings.demo_max_bytes):
            continue
        relative = path.relative_to(root)
        rel_text = relative.as_posix()
        demo_family = relative.parts[0] if len(relative.parts) > 1 else "root"
        yield CatalogEntry(
            id=f"demo:{rel_text}",
            source="demo",
            category=f"demo/{demo_family}",
            status="official",
            path=str(path.resolve()),
            relative_path=rel_text,
            title=_title(path),
            tags=_tags(relative),
            size_bytes=path.stat().st_size,
        )


def build_catalog(settings: Settings) -> dict:
    entries = [*iter_projectskill(settings), *iter_demos(settings)]
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "demo_max_bytes": settings.demo_max_bytes,
        "counts_by_status": counts,
        "entries": [entry.to_dict() for entry in entries],
    }


def save_catalog(settings: Settings, catalog: dict) -> Path:
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    target = settings.catalog_path
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def load_catalog(settings: Settings) -> dict:
    return json.loads(settings.catalog_path.read_text(encoding="utf-8"))

