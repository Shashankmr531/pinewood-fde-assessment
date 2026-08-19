from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .utils import file_sha256, load_manifest, parse_file_name, save_manifest, utc_now


def build_bronze(paths: dict, run_id: str):
        manifest = load_manifest(paths["manifest_path"])
        run_log = []
        files = sorted(paths["data_dir"].glob("*.csv"))
        ingested_files = skipped_files = rejected_files = 0

        for path in files:
            file_hash = file_sha256(path)
            record = manifest.get(path.name)
            if record and record.get("file_hash") == file_hash:
                run_log.append({
                    "source": "n/a", "source_table": path.name, "file_name": path.name,
                    "file_hash": file_hash, "rows_in": record.get("rows_in", 0),
                    "rows_loaded": 0, "rows_rejected": 0, "status": "skipped",
                    "notes": "already processed; no new data to ingest",
                })
                skipped_files += 1
                continue

            try:
                source, table, period = parse_file_name(path)
                raw_df = pd.read_csv(path, dtype=str, keep_default_na=False).copy()
                raw_df["ingestion_source"] = source
                raw_df["ingestion_table"] = table
                raw_df["ingestion_period"] = period
                raw_df["ingestion_file"] = path.name
                raw_df["ingestion_file_hash"] = file_hash
                raw_df["ingested_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                output_path = paths["bronze_dir"] / source / f"{source}_{table}_{period}.parquet"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                raw_df.to_parquet(output_path, index=False)
                manifest[path.name] = {
                    "file_hash": file_hash, "source": source, "table": table,
                    "period": period, "rows_in": len(raw_df),
                    "ingested_at_utc": raw_df["ingested_at_utc"].iloc[0],
                }
                run_log.append({
                    "source": source, "source_table": f"{source}.{table}", "file_name": path.name,
                    "file_hash": file_hash, "rows_in": len(raw_df), "rows_loaded": len(raw_df),
                    "rows_rejected": 0, "status": "processed",
                    "notes": "raw parquet written to bronze layer",
                })
                ingested_files += 1
            except Exception as exc:
                run_log.append({
                    "source": "n/a", "source_table": path.name, "file_name": path.name,
                    "file_hash": file_hash, "rows_in": 0, "rows_loaded": 0,
                    "rows_rejected": 1, "status": "rejected", "notes": str(exc),
                })
                rejected_files += 1

        save_manifest(paths["manifest_path"], manifest)
        log_df = pd.DataFrame(run_log)
        log_df.insert(0, "run_id", run_id)
        log_df.insert(1, "logged_at_utc", utc_now())
        log_df.to_csv(paths["run_log_path"], index=False)

        if ingested_files == 0 and skipped_files == 0 and rejected_files == 0:
            print("No source files detected. Nothing to process.")
        elif ingested_files == 0 and skipped_files > 0 and rejected_files == 0:
            print(f"No new source files detected. {skipped_files} file(s) already processed; nothing new to ingest.")
        else:
            print(f"Processed {ingested_files} new file(s), skipped {skipped_files} already-processed file(s), rejected {rejected_files} file(s).")
        return run_log
