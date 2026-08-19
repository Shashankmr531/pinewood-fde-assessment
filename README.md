# Pinewood Senior Living Data & Analytics Assessment

This repo contains a rerunnable Python ETL pipeline, a Gold-layer SQL model, and a Power BI project stub for the Pinewood COO dashboard.

## Project structure

- `data/candidate_package/data/` - extracted source CSVs from the provided Pinewood dataset
- `pipeline/run_pipeline.py` - thin executable entry point
- `pipeline/orchestrator.py` - `PipelineOrchestrator` stage sequencing, lifecycle, and audit logging
- `pipeline/bronze.py` - source-file ingestion and Bronze Parquet creation
- `pipeline/silver.py` - source-specific cleaning and Silver table creation
- `pipeline/gold.py` - Gold dimensions and fact modeling
- `pipeline/config.py`, `pipeline/constants.py`, `pipeline/utils.py` - shared configuration, mappings, and infrastructure helpers
- `pipeline/warehouse/` - generated DuckDB database, parquet bronze files, manifest, and run log
- `sql/ddl_gold.sql` - Gold-layer DDL
- `sql/queries_gold.sql` - occupancy, move-out, and incident-rate SQL
- `powerbi/` - Power BI project metadata for the COO dashboard

## Setup and run

On a fresh machine:

```bash
python -m pip install -r requirements.txt
python pipeline/run_pipeline.py
```

This command creates or refreshes the warehouse database at `pipeline/warehouse/pinewood.duckdb`, writes raw bronze parquet files under `pipeline/warehouse/bronze`, and rebuilds the Silver and Gold marts in DuckDB.

The pipeline uses a simple ingestion manifest (`pipeline/warehouse/ingestion_manifest.json`) to detect files that were already processed. If the same CSV hash is seen again, it is marked as `skipped`; otherwise it is ingested as `processed`. Files that fail validation are written to the run log as `rejected`.

Detailed audit logs are also written to `pipeline/warehouse/`:

- `run_log.csv` - latest source-file results, including processed, skipped, and rejected files
- `pipeline_runs.csv` - append-only run history with duration, status, and failed stage
- `stage_run_log.csv` - Bronze, Silver, and Gold timing and row-count summaries
- `table_run_log.csv` - Silver and Gold table row counts for each run

## Architecture and tradeoffs

- Bronze: stores raw CSVs in Parquet plus file metadata for traceability and reruns.
- Silver: cleans and normalizes source fields without altering the reported business event semantics.
- Gold: creates a star schema that is easy for Power BI and SQL consumers.

Tradeoff: I chose DuckDB as the warehouse because it is local, fast, and does not require a cloud account. The resulting Gold tables are intentionally compact and denormalized so they can be consumed directly by Power BI and by SQL analysts.

## Gold schema and grain

Fact tables:

- `gold.fact_occupancy_monthly`
  - Grain: one row per community per month
  - Purpose: occupancy rate and unit utilization by month

- `gold.fact_move_out`
  - Grain: one row per move-out lease record
  - Purpose: move-out reasons, volumes, and trailing-period trend analysis

- `gold.fact_incident_care_monthly`
  - Grain: one row per community, care level, and month
  - Purpose: incident counts and resident-day denominators for incident-rate reporting

Dimension tables:

- `gold.dim_community`
- `gold.dim_date`
- `gold.dim_care_level`

## DAX measures

These are the four measures I would include in the Power BI report:

1. Current occupancy percent
   - `Current Occupancy % = DIVIDE(SUM(fact_occupancy_monthly[occupied_units]), SUM(fact_occupancy_monthly[total_units]))`
   - This measures the current utilization of rooms in the latest month in the model.

2. Move-out rate percent for the trailing 90 days
   - `Trailing 90D Move-Out Rate % = DIVIDE(CALCULATE(COUNT(fact_move_out[move_out_id]), DATESINPERIOD(dim_date[month_start], MAX(dim_date[month_start]), -90, DAY)), CALCULATE(SUM(fact_occupancy_monthly[occupied_units]), DATESINPERIOD(dim_date[month_start], MAX(dim_date[month_start]), -90, DAY)))`
   - This highlights the rate of residents departing over the most recent 90-day period.

3. Incident rate per 100 resident-days
   - `Incident Rate per 100 Resident-Days = DIVIDE(SUM(fact_incident_care_monthly[incident_count]), SUM(fact_incident_care_monthly[resident_days])) * 100`
   - This normalizes incident volume to resident-days so communities with different census sizes are comparable.

4. Time intelligence measure (YTD occupancy)
   - `YTD Occupancy % = CALCULATE([Current Occupancy %], DATESYTD(dim_date[month_start]))`
   - This lets the COO compare this year-to-date occupancy to the monthly trend and to prior periods.

## Power BI model and RLS

Recommended relationships:

- `dim_community[community_id]` -> `fact_occupancy_monthly[community_id]` (single direction, many-to-one)
- `dim_date[month_start]` -> `fact_occupancy_monthly[month_start]` (single direction, many-to-one)
- `dim_community[community_id]` -> `fact_move_out[community_id]` (single direction, many-to-one)
- `dim_community[community_id]` -> `fact_incident_care_monthly[community_id]` (single direction, many-to-one)
- `dim_date[month_start]` -> `fact_incident_care_monthly[month_start]` (single direction, many-to-one)
- `dim_care_level[care_level_code]` -> `fact_incident_care_monthly[care_level]` (single direction, many-to-one)

Direction is from the dimension to the fact table because a dimension row is the master lookup and the fact table stores the events and measures. This keeps the model simple and prevents ambiguous filtering paths.

RLS:

- Regional Director: filter on `dim_community[region]` using a user-to-region mapping table.
- Community Executive Director: filter on `dim_community[community_id]` based on the assigned community.

The source-controlled Power BI metadata is in `powerbi/pinewood_coo_dashboard.pbip`.

## Anomalies Found

1. Care level values drift across source files (e.g., `Assisted Living`, `Independent`, `Memory`, `AL`, `IL`, `MC`).
   - Handling: fixed in the Silver layer by normalizing to the canonical values `IL`, `AL`, `MC`.
   - Why: the same business concept appears with multiple labels, which would break the Gold model and comparison logic.

2. ADP `hourly_rate` is stored as a Python dict-like string instead of a numeric value.
   - Handling: fixed in the pipeline by parsing the JSON-like string and extracting the rate for each role.
   - Why: Power BI and SQL cannot aggregate a string dictionary as a dollar value.

3. `pcc_residents` has schema drift: the April file adds a `mobility_status` column that other months do not have.
   - Handling: fixed in Silver by reindexing to a common schema and tolerating missing columns.
   - Why: monthly source exports are not perfectly consistent and a strict loader would fail without a staging guardrail.

4. Duplicate resident rows appear when a snapshot is re-exported or the file contains backfills.
   - Handling: fixed by deduplicating on `resident_id` + `snapshot_month` at the Silver layer.
   - Why: duplicate snapshots would inflate active resident counts and distort occupancy and resident-day denominators.

5. Some `pcc_care_history` rows have blank `previous_level` (admissions) and are not true transitions.
   - Handling: preserved, but they are treated as admission rows rather than as care-level changes in the model.
   - Why: the blank value does not mean a change; it means the resident entered the community at that level.

6. `move_out_reason` values vary in casing and wording (for example `Higher Care Needed` vs `Health Decline` vs `care transition`).
   - Handling: fixed by mapping the variants to canonical values in the Silver layer.
   - Why: the executive dashboard needs a consistent reason taxonomy for comparisons and ranking.

7. Some resident discharge dates are blank or invalid and need quarantine logic.
   - Handling: invalid dates are quarantined or nullified in the pipeline; valid rows remain in Silver.
   - Why: a bad date would create false resident-days or occupancy spikes and should not be silently coerced into a wrong value.

## Walkthrough

Recorded walkthrough link: https://example.com/loom-placeholder

The final walkthrough should cover:
- architecture and tradeoffs
- a live pipeline run
- a short code walk-through
- the Power BI dashboard and RLS switching
- anomalies and decisions

## SQL notes

The Gold DDL is in `sql/ddl_gold.sql` and the query examples are in `sql/queries_gold.sql`.

## Notes

This project is intentionally designed to be locally runnable and source-controlled without a cloud account. The executive dashboard needs a Windows Power BI Desktop installation to open the `.pbip` project and test the roles directly.
