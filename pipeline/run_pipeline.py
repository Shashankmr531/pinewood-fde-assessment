from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from pipeline.bronze import build_bronze
from pipeline.config import build_paths
from pipeline.gold import build_gold
from pipeline.silver import build_silver
from pipeline.utils import append_log_rows, table_row_counts, utc_now


class PipelineRunner:
    def __init__(self):
        self.paths = build_paths(Path(__file__).resolve().parents[1])

    def run(self):
        self._prepare_directories()
        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        run_started_at = utc_now()
        run_timer = time.perf_counter()
        stage_logs = []
        table_logs = []
        db = None
        current_stage = "initialization"
        run_status = "succeeded"
        error_message = ""
        run_log = []

        try:
            current_stage = "bronze"
            stage_timer = time.perf_counter()
            stage_started_at = utc_now()
            run_log = build_bronze(self.paths, run_id)
            stage_logs.append(self._stage_record(run_id, current_stage, stage_started_at, stage_timer, sum(row["rows_in"] for row in run_log), sum(row["rows_loaded"] for row in run_log), f"processed={sum(row['status'] == 'processed' for row in run_log)}, skipped={sum(row['status'] == 'skipped' for row in run_log)}, rejected={sum(row['status'] == 'rejected' for row in run_log)}"))

            current_stage = "silver"
            stage_timer = time.perf_counter()
            stage_started_at = utc_now()
            db = build_silver(self.paths)
            silver_tables = table_row_counts(db, ["silver"])
            table_logs.extend({"run_id": run_id, **row, "status": "succeeded"} for row in silver_tables)
            stage_logs.append(self._stage_record(run_id, current_stage, stage_started_at, stage_timer, sum(row["rows_in"] for row in run_log), sum(row["rows_written"] for row in silver_tables), f"tables={len(silver_tables)}"))

            current_stage = "gold"
            stage_timer = time.perf_counter()
            stage_started_at = utc_now()
            build_gold(db)
            gold_tables = table_row_counts(db, ["gold"])
            table_logs.extend({"run_id": run_id, **row, "status": "succeeded"} for row in gold_tables)
            stage_logs.append(self._stage_record(run_id, current_stage, stage_started_at, stage_timer, sum(row["rows_written"] for row in silver_tables), sum(row["rows_written"] for row in gold_tables), f"tables={len(gold_tables)}"))
        except Exception as exc:
            run_status = "failed"
            error_message = f"{type(exc).__name__}: {exc}"
            stage_logs.append({"run_id": run_id, "stage": current_stage, "status": "failed", "started_at_utc": run_started_at, "completed_at_utc": utc_now(), "duration_seconds": round(time.perf_counter() - run_timer, 3), "input_rows": 0, "output_rows": 0, "details": error_message})
        finally:
            if db is not None:
                db.close()
            self._write_audit_logs(run_id, run_started_at, run_timer, run_status, current_stage, error_message, stage_logs, table_logs)

        if run_status == "failed":
            print(f"\nPinewood ETL run {run_id} failed in {current_stage}: {error_message}")
            raise RuntimeError(error_message)

        summary = pd.DataFrame(run_log).groupby("status").agg(rows_rejected=("rows_rejected", "sum"), rows_loaded=("rows_loaded", "sum")).reset_index()
        print(f"\nPinewood ETL run {run_id} complete.")
        print(summary.to_string(index=False))
        print("\nDetailed logs written to pipeline/warehouse/run_log.csv, pipeline/warehouse/stage_run_log.csv, pipeline/warehouse/table_run_log.csv, and pipeline/warehouse/pipeline_runs.csv")
        print("Gold tables written to pipeline/warehouse/pinewood.duckdb")

    def _prepare_directories(self):
        self.paths["warehouse_dir"].mkdir(parents=True, exist_ok=True)
        self.paths["bronze_dir"].mkdir(parents=True, exist_ok=True)
        self.paths["silver_dir"].mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _stage_record(run_id, stage, started_at, stage_timer, input_rows, output_rows, details):
        return {"run_id": run_id, "stage": stage, "status": "succeeded", "started_at_utc": started_at, "completed_at_utc": utc_now(), "duration_seconds": round(time.perf_counter() - stage_timer, 3), "input_rows": input_rows, "output_rows": output_rows, "details": details}

    def _write_audit_logs(self, run_id, started_at, run_timer, status, failed_stage, error, stage_logs, table_logs):
        append_log_rows(self.paths["pipeline_runs_path"], [{"run_id": run_id, "started_at_utc": started_at, "completed_at_utc": utc_now(), "duration_seconds": round(time.perf_counter() - run_timer, 3), "status": status, "failed_stage": failed_stage if status == "failed" else "", "error": error}], ["run_id", "started_at_utc", "completed_at_utc", "duration_seconds", "status", "failed_stage", "error"])
        append_log_rows(self.paths["table_run_log_path"], table_logs, ["run_id", "layer", "table_name", "rows_written", "status"])
        append_log_rows(self.paths["stage_run_log_path"], stage_logs, ["run_id", "stage", "status", "started_at_utc", "completed_at_utc", "duration_seconds", "input_rows", "output_rows", "details"])


if __name__ == "__main__":
    PipelineRunner().run()
