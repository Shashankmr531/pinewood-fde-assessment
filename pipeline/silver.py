from __future__ import annotations

import json
from typing import Iterable

import duckdb
import pandas as pd

from .constants import MOVE_REASON_MAP
from .utils import normalize_care_level, normalize_date, normalize_text, parse_file_name


def reindex_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    return df.reindex(columns=list(columns), copy=False)


def clean_pcc_residents(df, period):
    df = reindex_columns(df, ["resident_id", "community_id", "first_name", "last_name", "dob", "gender", "admit_date", "discharge_date", "care_level", "acuity_score", "mobility_status"])
    df["snapshot_month"] = pd.to_datetime(period, format="%Y_%m").strftime("%Y-%m-01")
    for column in ["resident_id", "community_id", "first_name", "last_name"]:
        df[column] = df[column].apply(normalize_text)
    df["gender"] = df["gender"].apply(lambda value: normalize_text(value).upper() if normalize_text(value) else None)
    for column in ["dob", "admit_date", "discharge_date"]:
        df[column] = df[column].apply(normalize_date)
    df["care_level"] = df["care_level"].apply(normalize_care_level)
    df["acuity_score"] = pd.to_numeric(df["acuity_score"], errors="coerce").astype("Int64")
    return df.dropna(subset=["resident_id", "community_id"], how="any").drop_duplicates(subset=["resident_id", "snapshot_month"], keep="last").sort_values(["snapshot_month", "resident_id"]).reset_index(drop=True)


def clean_pcc_incidents(df):
    df = reindex_columns(df, ["incident_id", "resident_id", "community_id", "incident_date", "incident_type", "severity", "reported_by"])
    for column in ["incident_id", "resident_id", "community_id", "reported_by"]:
        df[column] = df[column].apply(normalize_text)
    df["incident_date"] = df["incident_date"].apply(normalize_date)
    df["incident_type"] = df["incident_type"].apply(lambda value: normalize_text(value).title() if normalize_text(value) else None)
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce").astype("Int64")
    return df.dropna(subset=["incident_id", "resident_id", "community_id", "incident_date"], how="any").drop_duplicates(subset=["incident_id"], keep="last").sort_values("incident_date").reset_index(drop=True)


def clean_pcc_care_history(df):
    df = reindex_columns(df, ["resident_id", "change_date", "previous_level", "new_level", "reason"])
    df["resident_id"] = df["resident_id"].apply(normalize_text)
    df["change_date"] = df["change_date"].apply(normalize_date)
    df["previous_level"] = df["previous_level"].apply(normalize_care_level)
    df["new_level"] = df["new_level"].apply(normalize_care_level)
    df["reason"] = df["reason"].apply(normalize_text)
    return df.dropna(subset=["resident_id", "change_date", "new_level"], how="any").drop_duplicates(subset=["resident_id", "change_date", "new_level"], keep="last").sort_values(["resident_id", "change_date"]).reset_index(drop=True)


def clean_yardi_units(df):
    df = reindex_columns(df, ["unit_id", "community_id", "unit_type", "monthly_rent", "snapshot_date"])
    df["unit_id"] = df["unit_id"].apply(normalize_text)
    df["community_id"] = df["community_id"].apply(normalize_text)
    df["unit_type"] = df["unit_type"].apply(lambda value: normalize_text(value).upper() if normalize_text(value) else None)
    df["snapshot_date"] = df["snapshot_date"].apply(normalize_date)
    df["monthly_rent"] = pd.to_numeric(df["monthly_rent"], errors="coerce")
    return df.dropna(subset=["unit_id", "community_id", "snapshot_date"], how="any").drop_duplicates(subset=["unit_id", "snapshot_date"], keep="last").reset_index(drop=True)


def clean_yardi_leases(df):
    df = reindex_columns(df, ["lease_id", "resident_id", "unit_id", "community_id", "move_in_date", "move_out_date", "move_out_reason", "monthly_rate"])
    for column in ["lease_id", "resident_id", "unit_id", "community_id"]:
        df[column] = df[column].apply(normalize_text)
    for column in ["move_in_date", "move_out_date"]:
        df[column] = df[column].apply(normalize_date)
    df["move_out_reason"] = df["move_out_reason"].apply(lambda value: MOVE_REASON_MAP.get(normalize_text(value).lower(), normalize_text(value).title()) if normalize_text(value) else None)
    df["monthly_rate"] = pd.to_numeric(df["monthly_rate"], errors="coerce")
    return df.dropna(subset=["lease_id", "resident_id", "unit_id", "community_id"], how="any").drop_duplicates(subset=["lease_id"], keep="last").sort_values(["community_id", "move_out_date"]).reset_index(drop=True)


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


def clean_adp_shifts(df):
    df = reindex_columns(df, ["shift_id", "community_id", "employee_id", "role", "shift_date", "hours_worked", "hourly_rate"])
    for column in ["shift_id", "community_id", "employee_id"]:
        df[column] = df[column].apply(normalize_text)
    df["role"] = df["role"].apply(lambda value: normalize_text(value).title() if normalize_text(value) else None)
    df["shift_date"] = df["shift_date"].apply(normalize_date)
    df["hours_worked"] = pd.to_numeric(df["hours_worked"], errors="coerce")
    df["hourly_rate"] = df.apply(lambda row: parse_hourly_rate(row["hourly_rate"], row["role"]), axis=1)
    return df.dropna(subset=["shift_id", "community_id", "shift_date"], how="any").drop_duplicates(subset=["shift_id"], keep="last").sort_values(["community_id", "shift_date"]).reset_index(drop=True)


def clean_gbp_reviews(df):
    df = reindex_columns(df, ["review_id", "community_id", "review_date", "rating", "review_text", "response_text", "responded_at"])
    for column in ["review_id", "community_id", "review_text", "response_text"]:
        df[column] = df[column].apply(normalize_text)
    for column in ["review_date", "responded_at"]:
        df[column] = df[column].apply(normalize_date)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")
    return df.dropna(subset=["review_id", "community_id", "review_date"], how="any").drop_duplicates(subset=["review_id"], keep="last").sort_values(["community_id", "review_date"]).reset_index(drop=True)


def clean_hubspot_leads(df):
    df = reindex_columns(df, ["lead_id", "community_id", "lead_source", "created_date", "tour_date", "deposit_date", "move_in_date", "status", "lost_reason"])
    for column in ["lead_id", "community_id"]:
        df[column] = df[column].apply(normalize_text)
    for column in ["created_date", "tour_date", "deposit_date", "move_in_date"]:
        df[column] = df[column].apply(normalize_date)
    for column in ["lead_source", "status", "lost_reason"]:
        df[column] = df[column].apply(lambda value: normalize_text(value).title() if normalize_text(value) else None)
    return df.dropna(subset=["lead_id", "community_id", "created_date"], how="any").drop_duplicates(subset=["lead_id"], keep="last").sort_values(["community_id", "created_date"]).reset_index(drop=True)


CLEANERS = {
    ("pcc", "residents"): lambda df, period: clean_pcc_residents(df, period),
    ("pcc", "incidents"): lambda df, period: clean_pcc_incidents(df),
    ("pcc", "care_history"): lambda df, period: clean_pcc_care_history(df),
    ("yardi", "units"): lambda df, period: clean_yardi_units(df),
    ("yardi", "leases"): lambda df, period: clean_yardi_leases(df),
    ("adp", "shifts"): lambda df, period: clean_adp_shifts(df),
    ("gbp", "reviews"): lambda df, period: clean_gbp_reviews(df),
    ("hubspot", "leads"): lambda df, period: clean_hubspot_leads(df),
}


def build_silver(paths: dict):
        frames = {}
        for path in sorted(paths["data_dir"].glob("*.csv")):
            source, table, period = parse_file_name(path)
            cleaner = CLEANERS.get((source, table))
            if cleaner is None:
                continue
            bronze_path = paths["bronze_dir"] / source / f"{source}_{table}_{period}.parquet"
            cleaned = cleaner(pd.read_parquet(bronze_path), period)
            frames.setdefault(f"{source}_{table}", []).append(cleaned)

        db = duckdb.connect(str(paths["db_path"]))
        db.execute("CREATE SCHEMA IF NOT EXISTS silver")
        for name, table_frames in frames.items():
            combined = pd.concat(table_frames, ignore_index=True)
            db.register(f"silver_{name}", combined)
            db.execute(f"CREATE OR REPLACE TABLE silver.{name} AS SELECT * FROM silver_{name}")
        return db
