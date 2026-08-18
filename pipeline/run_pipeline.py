from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "candidate_package" / "data"
WAREHOUSE_DIR = REPO_ROOT / "pipeline" / "warehouse"
BRONZE_DIR = WAREHOUSE_DIR / "bronze"
SILVER_DIR = WAREHOUSE_DIR / "silver"
DB_PATH = WAREHOUSE_DIR / "pinewood.duckdb"

SOURCE_TABLES = {
    "pcc": ["residents", "incidents", "care_history"],
    "yardi": ["units", "leases"],
    "adp": ["shifts"],
    "gbp": ["reviews"],
    "hubspot": ["leads"],
}
CARE_LEVEL_MAP = {
    "il": "IL",
    "independent": "IL",
    "independent living": "IL",
    "assisted": "AL",
    "assisted living": "AL",
    "al": "AL",
    "memory": "MC",
    "memory care": "MC",
    "mc": "MC",
    "nan": None,
    "": None,
}
MOVE_REASON_MAP = {
    "financial": "Financial",
    "higher care needed": "Higher Care Needed",
    "family decision": "Family Decision",
    "hospital transfer": "Hospital Transfer",
    "deceased": "Deceased",
    "dissatisfied": "Dissatisfied",
    "other": "Other",
    "care transition": "Higher Care Needed",
    "changed care level": "Higher Care Needed",
    "health decline": "Higher Care Needed",
    "affordability": "Financial",
    "": None,
    "nan": None,
}


def normalize_text(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None
    return text


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


def safe_float(value):
    text = normalize_text(value)
    if text is None:
        return None
    if text.startswith("{"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_file_name(path: Path):
    stem = path.name.replace(".csv", "")
    parts = stem.split("_")
    if len(parts) < 4:
        raise ValueError(f"Unexpected filename format: {path.name}")
    source = parts[0]
    table = "_".join(parts[1:-2])
    period = f"{parts[-2]}_{parts[-1]}"
    return source, table, period


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_directories():
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    SILVER_DIR.mkdir(parents=True, exist_ok=True)


def build_bronze():
    run_log = []
    files = sorted(DATA_DIR.glob("*.csv"))
    for path in files:
        source, table, period = parse_file_name(path)
        raw_df = pd.read_csv(path, dtype=str, keep_default_na=False)
        out_path = BRONZE_DIR / source / f"{source}_{table}_{period}.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw_df.to_parquet(out_path, index=False)
        run_log.append(
            {
                "source": source,
                "source_table": f"{source}.{table}",
                "file_name": path.name,
                "file_hash": file_sha256(path),
                "rows_in": len(raw_df),
                "rows_loaded": len(raw_df),
                "rows_rejected": 0,
                "status": "processed",
                "notes": "raw parquet written to bronze layer",
            }
        )
    log_path = WAREHOUSE_DIR / "run_log.csv"
    pd.DataFrame(run_log).to_csv(log_path, index=False)
    return run_log


def reindex_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    all_columns = list(columns)
    return df.reindex(columns=all_columns, copy=False)


def clean_pcc_residents(df: pd.DataFrame, period: str) -> pd.DataFrame:
    expected = [
        "resident_id",
        "community_id",
        "first_name",
        "last_name",
        "dob",
        "gender",
        "admit_date",
        "discharge_date",
        "care_level",
        "acuity_score",
        "mobility_status",
    ]
    df = reindex_columns(df, expected)
    df["snapshot_month"] = pd.to_datetime(period, format="%Y_%m").strftime("%Y-%m-01")
    df["gender"] = df["gender"].apply(lambda x: normalize_text(x).upper() if normalize_text(x) else None)
    df["resident_id"] = df["resident_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["last_name"] = df["last_name"].apply(normalize_text)
    df["first_name"] = df["first_name"].apply(normalize_text)
    df["dob"] = df["dob"].apply(normalize_date)
    df["admit_date"] = df["admit_date"].apply(normalize_date)
    df["discharge_date"] = df["discharge_date"].apply(normalize_date)
    df["care_level"] = df["care_level"].apply(normalize_care_level)
    df["acuity_score"] = pd.to_numeric(df["acuity_score"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["resident_id", "community_id"], how="any")
    df = df.drop_duplicates(subset=["resident_id", "snapshot_month"], keep="last").sort_values(["snapshot_month", "resident_id"]).reset_index(drop=True)
    return df


def clean_pcc_incidents(df: pd.DataFrame) -> pd.DataFrame:
    expected = ["incident_id", "resident_id", "community_id", "incident_date", "incident_type", "severity", "reported_by"]
    df = reindex_columns(df, expected)
    df["incident_id"] = df["incident_id"].apply(normalize_text)
    df["resident_id"] = df["resident_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["incident_date"] = df["incident_date"].apply(normalize_date)
    df["incident_type"] = df["incident_type"].apply(lambda x: normalize_text(x).title() if normalize_text(x) else None)
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce").astype("Int64")
    df["reported_by"] = df["reported_by"].apply(normalize_text)
    df = df.dropna(subset=["incident_id", "resident_id", "community_id", "incident_date"], how="any")
    df = df.drop_duplicates(subset=["incident_id"], keep="last").sort_values("incident_date").reset_index(drop=True)
    return df


def clean_pcc_care_history(df: pd.DataFrame) -> pd.DataFrame:
    expected = ["resident_id", "change_date", "previous_level", "new_level", "reason"]
    df = reindex_columns(df, expected)
    df["resident_id"] = df["resident_id"].apply(normalize_text)
    df["change_date"] = df["change_date"].apply(normalize_date)
    df["previous_level"] = df["previous_level"].apply(normalize_care_level)
    df["new_level"] = df["new_level"].apply(normalize_care_level)
    df["reason"] = df["reason"].apply(lambda x: normalize_text(x))
    df = df.dropna(subset=["resident_id", "change_date", "new_level"], how="any")
    df = df.drop_duplicates(subset=["resident_id", "change_date", "new_level"], keep="last").sort_values(["resident_id", "change_date"]).reset_index(drop=True)
    return df


def clean_yardi_units(df: pd.DataFrame) -> pd.DataFrame:
    expected = ["unit_id", "community_id", "unit_type", "monthly_rent", "snapshot_date"]
    df = reindex_columns(df, expected)
    df["unit_id"] = df["unit_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["unit_type"] = df["unit_type"].apply(lambda x: normalize_text(x).upper() if normalize_text(x) else None)
    df["snapshot_date"] = df["snapshot_date"].apply(normalize_date)
    df["monthly_rent"] = pd.to_numeric(df["monthly_rent"], errors="coerce")
    df = df.dropna(subset=["unit_id", "community_id", "snapshot_date"], how="any")
    df = df.drop_duplicates(subset=["unit_id", "snapshot_date"], keep="last").reset_index(drop=True)
    return df


def clean_yardi_leases(df: pd.DataFrame) -> pd.DataFrame:
    expected = ["lease_id", "resident_id", "unit_id", "community_id", "move_in_date", "move_out_date", "move_out_reason", "monthly_rate"]
    df = reindex_columns(df, expected)
    df["lease_id"] = df["lease_id"].apply(normalize_text)
    df["resident_id"] = df["resident_id"].apply(normalize_text)
    df["unit_id"] = df["unit_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["move_in_date"] = df["move_in_date"].apply(normalize_date)
    df["move_out_date"] = df["move_out_date"].apply(normalize_date)
    df["move_out_reason"] = df["move_out_reason"].apply(lambda x: MOVE_REASON_MAP.get(normalize_text(x).lower(), normalize_text(x).title()) if normalize_text(x) else None)
    df["monthly_rate"] = pd.to_numeric(df["monthly_rate"], errors="coerce")
    df = df.dropna(subset=["lease_id", "resident_id", "unit_id", "community_id"], how="any")
    df = df.drop_duplicates(subset=["lease_id"], keep="last").sort_values(["community_id", "move_out_date"]).reset_index(drop=True)
    return df


def parse_hourly_rate(value, role):
    raw = normalize_text(value)
    if raw is None:
        return None
    try:
        payload = json.loads(raw.replace("'", '"'))
        if isinstance(payload, dict):
            return float(payload.get(role, 0))
    except Exception:
        pass
    try:
        return float(raw)
    except ValueError:
        return None


def clean_adp_shifts(df: pd.DataFrame) -> pd.DataFrame:
    expected = ["shift_id", "community_id", "employee_id", "role", "shift_date", "hours_worked", "hourly_rate"]
    df = reindex_columns(df, expected)
    df["shift_id"] = df["shift_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["employee_id"] = df["employee_id"].apply(normalize_text)
    df["role"] = df["role"].apply(lambda x: normalize_text(x).title() if normalize_text(x) else None)
    df["shift_date"] = df["shift_date"].apply(normalize_date)
    df["hours_worked"] = pd.to_numeric(df["hours_worked"], errors="coerce")
    df["hourly_rate"] = df.apply(lambda row: parse_hourly_rate(row["hourly_rate"], row["role"]), axis=1)
    df = df.dropna(subset=["shift_id", "community_id", "shift_date"], how="any")
    df = df.drop_duplicates(subset=["shift_id"], keep="last").sort_values(["community_id", "shift_date"]).reset_index(drop=True)
    return df


def clean_gbp_reviews(df: pd.DataFrame) -> pd.DataFrame:
    expected = ["review_id", "community_id", "review_date", "rating", "review_text", "response_text", "responded_at"]
    df = reindex_columns(df, expected)
    df["review_id"] = df["review_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["review_date"] = df["review_date"].apply(normalize_date)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")
    df["review_text"] = df["review_text"].apply(normalize_text)
    df["response_text"] = df["response_text"].apply(normalize_text)
    df["responded_at"] = df["responded_at"].apply(normalize_date)
    df = df.dropna(subset=["review_id", "community_id", "review_date"], how="any")
    df = df.drop_duplicates(subset=["review_id"], keep="last").sort_values(["community_id", "review_date"]).reset_index(drop=True)
    return df


def clean_hubspot_leads(df: pd.DataFrame) -> pd.DataFrame:
    expected = ["lead_id", "community_id", "lead_source", "created_date", "tour_date", "deposit_date", "move_in_date", "status", "lost_reason"]
    df = reindex_columns(df, expected)
    df["lead_id"] = df["lead_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["lead_source"] = df["lead_source"].apply(lambda x: normalize_text(x).title() if normalize_text(x) else None)
    for col in ["created_date", "tour_date", "deposit_date", "move_in_date"]:
        df[col] = df[col].apply(normalize_date)
    df["status"] = df["status"].apply(lambda x: normalize_text(x).title() if normalize_text(x) else None)
    df["lost_reason"] = df["lost_reason"].apply(lambda x: normalize_text(x).title() if normalize_text(x) else None)
    df = df.dropna(subset=["lead_id", "community_id", "created_date"], how="any")
    df = df.drop_duplicates(subset=["lead_id"], keep="last").sort_values(["community_id", "created_date"]).reset_index(drop=True)
    return df


def build_silver():
    silver_frames = {}
    for path in sorted(DATA_DIR.glob("*.csv")):
        source, table, period = parse_file_name(path)
        raw_df = pd.read_parquet(BRONZE_DIR / source / f"{source}_{table}_{period}.parquet")
        if source == "pcc" and table == "residents":
            silver_df = clean_pcc_residents(raw_df, period)
        elif source == "pcc" and table == "incidents":
            silver_df = clean_pcc_incidents(raw_df)
        elif source == "pcc" and table == "care_history":
            silver_df = clean_pcc_care_history(raw_df)
        elif source == "yardi" and table == "units":
            silver_df = clean_yardi_units(raw_df)
        elif source == "yardi" and table == "leases":
            silver_df = clean_yardi_leases(raw_df)
        elif source == "adp" and table == "shifts":
            silver_df = clean_adp_shifts(raw_df)
        elif source == "gbp" and table == "reviews":
            silver_df = clean_gbp_reviews(raw_df)
        elif source == "hubspot" and table == "leads":
            silver_df = clean_hubspot_leads(raw_df)
        else:
            continue
        table_name = f"{source}_{table}"
        silver_frames.setdefault(table_name, []).append(silver_df)

    db = duckdb.connect(str(DB_PATH))
    db.execute("CREATE SCHEMA IF NOT EXISTS silver")
    for name, frames in silver_frames.items():
        combined = pd.concat(frames, ignore_index=True)
        full_name = f"silver.{name}"
        db.register(f"silver_{name}", combined)
        db.execute(f"CREATE OR REPLACE TABLE {full_name} AS SELECT * FROM silver_{name}")
    return db


def build_gold(db: duckdb.DuckDBPyConnection):
    db.execute("CREATE SCHEMA IF NOT EXISTS gold")

    community_map = [
        ("C001", "Pinewood Bend", "OR", "Pacific Northwest"),
        ("C002", "Pinewood Corvallis", "OR", "Pacific Northwest"),
        ("C003", "Pinewood Eugene", "OR", "Pacific Northwest"),
        ("C004", "Pinewood Salem", "OR", "Pacific Northwest"),
        ("C005", "Pinewood Phoenix", "AZ", "Southwest"),
        ("C006", "Pinewood Scottsdale", "AZ", "Southwest"),
        ("C007", "Pinewood Mesa", "AZ", "Southwest"),
        ("C008", "Pinewood Tucson", "AZ", "Southwest"),
        ("C009", "Pinewood Dallas", "TX", "South"),
        ("C010", "Pinewood Fort Worth", "TX", "South"),
        ("C011", "Pinewood Houston", "TX", "South"),
        ("C012", "Pinewood San Antonio", "TX", "South"),
        ("C013", "Pinewood Austin", "TX", "South"),
        ("C014", "Pinewood Round Rock", "TX", "South"),
    ]
    dim_community = pd.DataFrame(community_map, columns=["community_id", "community_name", "state", "region"])
    db.register("dim_community_df", dim_community)
    db.execute("CREATE OR REPLACE TABLE gold.dim_community AS SELECT * FROM dim_community_df")

    dim_date = pd.DataFrame({
        "month_start": pd.date_range("2025-01-01", "2025-06-01", freq="MS")
    })
    dim_date["year_num"] = dim_date["month_start"].dt.year
    dim_date["month_num"] = dim_date["month_start"].dt.month
    dim_date["month_name"] = dim_date["month_start"].dt.strftime("%b %Y")
    db.register("dim_date_df", dim_date)
    db.execute("CREATE OR REPLACE TABLE gold.dim_date AS SELECT * FROM dim_date_df")

    dim_care_level = pd.DataFrame([
        ("IL", "Independent Living"),
        ("AL", "Assisted Living"),
        ("MC", "Memory Care"),
    ], columns=["care_level_code", "care_level_name"])
    db.register("dim_care_level_df", dim_care_level)
    db.execute("CREATE OR REPLACE TABLE gold.dim_care_level AS SELECT * FROM dim_care_level_df")

    units = db.sql("SELECT community_id, CAST(snapshot_date AS DATE) AS snapshot_date, COUNT(*) AS total_units FROM silver.yardi_units WHERE community_id IN ('C001','C002','C003','C004','C005','C006','C007','C008','C009','C010','C011','C012','C013','C014') GROUP BY 1,2 ORDER BY 1,2").df()
    units["snapshot_month"] = pd.to_datetime(units["snapshot_date"]).dt.to_period("M").dt.to_timestamp()
    monthly_units = units.groupby(["community_id", "snapshot_month"], as_index=False)["total_units"].sum()

    active_residents = db.sql("SELECT resident_id, community_id, CAST(snapshot_month AS DATE) AS snapshot_month FROM silver.pcc_residents WHERE community_id IN ('C001','C002','C003','C004','C005','C006','C007','C008','C009','C010','C011','C012','C013','C014')").df()
    active_residents["snapshot_month"] = pd.to_datetime(active_residents["snapshot_month"], errors="coerce")
    month_starts = pd.date_range("2025-01-01", "2025-06-01", freq="MS")

    occ_rows = []
    for month_start in month_starts:
        for community in dim_community["community_id"].tolist():
            resident_count = int(active_residents[(active_residents["community_id"] == community) & (active_residents["snapshot_month"] == month_start)]["resident_id"].nunique())
            total_units = monthly_units[(monthly_units["community_id"] == community) & (monthly_units["snapshot_month"] == month_start)]["total_units"].sum()
            total_units = int(total_units) if pd.notna(total_units) else 0
            occupancy_pct = (resident_count / total_units) if total_units else 0.0
            occ_rows.append({
                "community_id": community,
                "month_start": month_start.strftime("%Y-%m-%d"),
                "occupied_units": resident_count,
                "total_units": total_units,
                "occupancy_pct": float(round(occupancy_pct, 4)),
            })
    fact_occupancy = pd.DataFrame(occ_rows)
    db.register("fact_occupancy_df", fact_occupancy)
    db.execute("CREATE OR REPLACE TABLE gold.fact_occupancy_monthly AS SELECT * FROM fact_occupancy_df")

    move_outs = db.sql("SELECT lease_id AS move_out_id, resident_id, community_id, CAST(move_out_date AS DATE) AS move_out_date, move_out_reason FROM silver.yardi_leases WHERE move_out_date IS NOT NULL").df()
    move_outs["move_out_month"] = pd.to_datetime(move_outs["move_out_date"]).dt.to_period("M").dt.to_timestamp()
    db.register("fact_move_out_df", move_outs)
    db.execute("CREATE OR REPLACE TABLE gold.fact_move_out AS SELECT * FROM fact_move_out_df")

    incidents = db.sql("SELECT incident_id, resident_id, community_id, CAST(incident_date AS DATE) AS incident_date, incident_type, severity FROM silver.pcc_incidents").df()
    incidents["incident_date"] = pd.to_datetime(incidents["incident_date"], errors="coerce")
    care_history = db.sql("SELECT resident_id, CAST(change_date AS DATE) AS change_date, new_level AS care_level FROM silver.pcc_care_history").df()
    care_history["change_date"] = pd.to_datetime(care_history["change_date"], errors="coerce")
    residents = db.sql("SELECT resident_id, community_id, care_level, CAST(snapshot_month AS DATE) AS snapshot_month FROM silver.pcc_residents").df()
    residents["snapshot_month"] = pd.to_datetime(residents["snapshot_month"], errors="coerce")

    assigned = []
    for _, row in incidents.iterrows():
        resident_id = row["resident_id"]
        incident_date = row["incident_date"]
        history = care_history[(care_history["resident_id"] == resident_id) & (care_history["change_date"] <= incident_date)]
        if not history.empty:
            care_level = history.sort_values("change_date").tail(1)["care_level"].iloc[0]
        else:
            resident_snapshot = residents[(residents["resident_id"] == resident_id) & (residents["snapshot_month"] <= incident_date)]
            care_level = resident_snapshot.sort_values("snapshot_month").tail(1)["care_level"].iloc[0] if not resident_snapshot.empty else None
        assigned.append({
            "incident_id": row["incident_id"],
            "resident_id": resident_id,
            "community_id": row["community_id"],
            "incident_date": incident_date,
            "care_level": care_level,
        })
    assigned_df = pd.DataFrame(assigned)
    if not assigned_df.empty:
        assigned_df["month_start"] = assigned_df["incident_date"].dt.to_period("M").dt.to_timestamp()
        incident_counts = assigned_df.groupby(["community_id", "care_level", "month_start"], as_index=False).size().rename(columns={"size": "incident_count"})
    else:
        incident_counts = pd.DataFrame(columns=["community_id", "care_level", "month_start", "incident_count"])

    resident_days = []
    active_residents = db.sql("SELECT resident_id, community_id, care_level, CAST(snapshot_month AS DATE) AS snapshot_month FROM silver.pcc_residents").df()
    active_residents["snapshot_month"] = pd.to_datetime(active_residents["snapshot_month"], errors="coerce")
    for month_start in month_starts:
        month_end = month_start + pd.offsets.MonthEnd(0)
        month_days = (month_end - month_start).days + 1
        for community in dim_community["community_id"].tolist():
            elig = active_residents[(active_residents["community_id"] == community) & (active_residents["snapshot_month"] == month_start)]
            for care_level in ["IL", "AL", "MC"]:
                count = int((elig["care_level"] == care_level).sum())
                resident_days.append({
                    "community_id": community,
                    "care_level": care_level,
                    "month_start": month_start.strftime("%Y-%m-%d"),
                    "resident_days": count * month_days,
                })
    resident_days_df = pd.DataFrame(resident_days)
    resident_days_df["month_start"] = pd.to_datetime(resident_days_df["month_start"], errors="coerce")
    incident_counts["month_start"] = pd.to_datetime(incident_counts["month_start"], errors="coerce")
    incident_rate_df = incident_counts.merge(resident_days_df, on=["community_id", "care_level", "month_start"], how="outer")
    incident_rate_df["incident_count"] = incident_rate_df["incident_count"].fillna(0).astype(int)
    incident_rate_df["resident_days"] = incident_rate_df["resident_days"].fillna(0).astype(int)
    incident_rate_df["incident_rate_per_100_resident_days"] = (incident_rate_df["incident_count"] / incident_rate_df["resident_days"] * 100).replace([float("inf"), float("-inf")], 0.0).fillna(0.0)
    incident_rate_df["month_start"] = incident_rate_df["month_start"].dt.strftime("%Y-%m-%d")
    incident_rate_df = incident_rate_df[["community_id", "care_level", "month_start", "incident_count", "resident_days", "incident_rate_per_100_resident_days"]]
    db.register("fact_incident_rate_df", incident_rate_df)
    db.execute("CREATE OR REPLACE TABLE gold.fact_incident_care_monthly AS SELECT * FROM fact_incident_rate_df")


def main():
    ensure_directories()
    run_log = build_bronze()
    db = build_silver()
    build_gold(db)
    db.close()

    log_df = pd.DataFrame(run_log)
    log_df["status"] = log_df["status"].replace({"processed": "processed"})
    summary = log_df.groupby("status").agg(rows_rejected=("rows_rejected", "sum"), rows_loaded=("rows_loaded", "sum")).reset_index()
    print("\nPinewood ETL run complete.")
    print(summary.to_string(index=False))
    print("\nRun log written to pipeline/warehouse/run_log.csv")
    print("Gold tables written to pipeline/warehouse/pinewood.duckdb")


if __name__ == "__main__":
    main()
