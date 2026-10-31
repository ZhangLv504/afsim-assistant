from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable

from .config import Settings


DEFAULT_STATUSES = ("official", "validated", "verified")


def _read_document(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rebuild_index(settings: Settings, catalog: dict) -> dict:
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    target = settings.index_path
    temporary = target.with_suffix(".db.tmp")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    indexed = 0
    bytes_indexed = 0
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE documents USING fts5(
                doc_id UNINDEXED,
                source UNINDEXED,
                status UNINDEXED,
                category UNINDEXED,
                path UNINDEXED,
                title,
                tags,
                content,
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
        rows = []
        for entry in catalog.get("entries", []):
            if entry.get("status") == "excluded":
                continue
            content = _read_document(entry["path"])
            if not content:
                continue
            rows.append(
                (
                    entry["id"],
                    entry["source"],
                    entry["status"],
                    entry["category"],
                    entry["path"],
                    entry["title"],
                    " ".join(entry.get("tags") or []),
                    content,
                )
            )
            indexed += 1
            bytes_indexed += len(content.encode("utf-8"))
            if len(rows) >= 250:
                connection.executemany(
                    "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
                )
                rows.clear()
        if rows:
            connection.executemany(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
            )
        connection.commit()
    finally:
        connection.close()
    if target.exists():
        target.unlink()
    temporary.replace(target)
    return {"documents_indexed": indexed, "bytes_indexed": bytes_indexed, "path": str(target)}


def _safe_match_query(query: str) -> str:
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not tokens:
        raise ValueError("search query contains no searchable terms")
    return " AND ".join(f'"{token}"' for token in tokens[:20])


def search(
    settings: Settings,
    query: str,
    *,
    statuses: Iterable[str] = DEFAULT_STATUSES,
    limit: int = 8,
) -> list[dict]:
    selected = tuple(dict.fromkeys(str(item) for item in statuses))
    if not selected:
        return []
    placeholders = ",".join("?" for _ in selected)
    sql = f"""
        SELECT
            doc_id, source, status, category, path, title,
            snippet(documents, 7, '[', ']', ' ... ', 28) AS excerpt,
            bm25(documents, 0.0, 0.0, 0.0, 0.0, 0.0, 5.0, 2.0, 1.0) AS score
        FROM documents
        WHERE documents MATCH ? AND status IN ({placeholders})
        ORDER BY score
        LIMIT ?
    """
    connection = sqlite3.connect(settings.index_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            sql,
            (_safe_match_query(query), *selected, max(1, min(int(limit), 50))),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()

