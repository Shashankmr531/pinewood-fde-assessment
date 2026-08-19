from __future__ import annotations

import duckdb
import pandas as pd

from .constants import CARE_LEVELS, COMMUNITY_IDS, COMMUNITIES


def build_gold(db: duckdb.DuckDBPyConnection):
        db.execute("CREATE SCHEMA IF NOT EXISTS gold")
        community_df = pd.DataFrame(COMMUNITIES, columns=["community_id", "community_name", "state", "region"])
        db.register("dim_community_df", community_df)
        db.execute("CREATE OR REPLACE TABLE gold.dim_community AS SELECT * FROM dim_community_df")

        date_df = pd.DataFrame({"month_start": pd.date_range("2025-01-01", "2025-06-01", freq="MS")})
        date_df["year_num"] = date_df["month_start"].dt.year
        date_df["month_num"] = date_df["month_start"].dt.month
        date_df["month_name"] = date_df["month_start"].dt.strftime("%b %Y")
        db.register("dim_date_df", date_df)
        db.execute("CREATE OR REPLACE TABLE gold.dim_date AS SELECT * FROM dim_date_df")

        care_df = pd.DataFrame([(code, name) for code, name in [("IL", "Independent Living"), ("AL", "Assisted Living"), ("MC", "Memory Care")]], columns=["care_level_code", "care_level_name"])
        db.register("dim_care_level_df", care_df)
        db.execute("CREATE OR REPLACE TABLE gold.dim_care_level AS SELECT * FROM dim_care_level_df")

        units = db.sql("SELECT community_id, CAST(snapshot_date AS DATE) AS snapshot_date, COUNT(*) AS total_units FROM silver.yardi_units WHERE community_id IN (" + ",".join(f"'{value}'" for value in COMMUNITY_IDS) + ") GROUP BY 1,2 ORDER BY 1,2").df()
        units["snapshot_month"] = pd.to_datetime(units["snapshot_date"]).dt.to_period("M").dt.to_timestamp()
        monthly_units = units.groupby(["community_id", "snapshot_month"], as_index=False)["total_units"].sum()

        active_residents = db.sql("SELECT resident_id, community_id, CAST(snapshot_month AS DATE) AS snapshot_month FROM silver.pcc_residents WHERE community_id IN (" + ",".join(f"'{value}'" for value in COMMUNITY_IDS) + ")").df()
        active_residents["snapshot_month"] = pd.to_datetime(active_residents["snapshot_month"], errors="coerce")
        month_starts = pd.date_range("2025-01-01", "2025-06-01", freq="MS")
        occupancy_rows = []
        for month_start in month_starts:
            for community in community_df["community_id"].tolist():
                resident_count = int(active_residents[(active_residents["community_id"] == community) & (active_residents["snapshot_month"] == month_start)]["resident_id"].nunique())
                total_units = monthly_units[(monthly_units["community_id"] == community) & (monthly_units["snapshot_month"] == month_start)]["total_units"].sum()
                total_units = int(total_units) if pd.notna(total_units) else 0
                occupancy_rows.append({"community_id": community, "month_start": month_start.strftime("%Y-%m-%d"), "occupied_units": resident_count, "total_units": total_units, "occupancy_pct": float(round(resident_count / total_units, 4)) if total_units else 0.0})
        occupancy_df = pd.DataFrame(occupancy_rows)
        db.register("fact_occupancy_df", occupancy_df)
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
            history = care_history[(care_history["resident_id"] == row["resident_id"]) & (care_history["change_date"] <= row["incident_date"])]
            if not history.empty:
                care_level = history.sort_values("change_date").tail(1)["care_level"].iloc[0]
            else:
                snapshots = residents[(residents["resident_id"] == row["resident_id"]) & (residents["snapshot_month"] <= row["incident_date"])]
                care_level = snapshots.sort_values("snapshot_month").tail(1)["care_level"].iloc[0] if not snapshots.empty else None
            assigned.append({"incident_id": row["incident_id"], "resident_id": row["resident_id"], "community_id": row["community_id"], "incident_date": row["incident_date"], "care_level": care_level})
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
            month_days = (month_start + pd.offsets.MonthEnd(0) - month_start).days + 1
            for community in community_df["community_id"].tolist():
                eligible = active_residents[(active_residents["community_id"] == community) & (active_residents["snapshot_month"] == month_start)]
                for care_level in CARE_LEVELS:
                    resident_days.append({"community_id": community, "care_level": care_level, "month_start": month_start.strftime("%Y-%m-%d"), "resident_days": int((eligible["care_level"] == care_level).sum()) * month_days})
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
