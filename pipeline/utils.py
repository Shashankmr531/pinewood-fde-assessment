from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from .constants import CARE_LEVEL_MAP


def normalize_text(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    return None if text == "" or text.lower() in {"nan", "none", "null"} else text


def normalize_date(value):
    text = normalize_text(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            return pd.to_datetime(text, format=fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return pd.to_datetime(text, errors="coerce").strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_care_level(value):
    text = normalize_text(value)
    if text is None:
        return None
    return CARE_LEVEL_MAP.get(text.lower(), text.upper()[:2] if text.upper()[:2] in {"IL", "AL", "MC"} else None)


def parse_file_name(path: Path):
    parts = path.name.replace(".csv", "").split("_")
    if len(parts) < 4:
        raise ValueError(f"Unexpected filename format: {path.name}")
    return parts[0], "_".join(parts[1:-2]), f"{parts[-2]}_{parts[-1]}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_manifest(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_manifest(path: Path, manifest):
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def append_log_rows(path: Path, rows: list[dict], columns: list[str]):
    if not rows:
        return
    log_df = pd.DataFrame(rows).reindex(columns=columns)
    log_df.to_csv(path, mode="a", header=not path.exists(), index=False)


def table_row_counts(db: duckdb.DuckDBPyConnection, schemas: list[str]):
    rows = []
    for schema in schemas:
        tables = db.sql(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}' ORDER BY table_name").fetchall()
        for (table_name,) in tables:
            count = db.sql(f"SELECT COUNT(*) FROM {schema}.{table_name}").fetchone()[0]
            rows.append({"layer": schema, "table_name": table_name, "rows_written": count})
    return rows
