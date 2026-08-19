from pathlib import Path


def build_paths(repo_root: Path) -> dict[str, Path]:
    warehouse_dir = repo_root / "pipeline" / "warehouse"
    return {
        "repo_root": repo_root,
        "data_dir": repo_root / "data" / "candidate_package" / "data",
        "warehouse_dir": warehouse_dir,
        "bronze_dir": warehouse_dir / "bronze",
        "silver_dir": warehouse_dir / "silver",
        "db_path": warehouse_dir / "pinewood.duckdb",
        "manifest_path": warehouse_dir / "ingestion_manifest.json",
        "pipeline_runs_path": warehouse_dir / "pipeline_runs.csv",
        "table_run_log_path": warehouse_dir / "table_run_log.csv",
        "stage_run_log_path": warehouse_dir / "stage_run_log.csv",
        "run_log_path": warehouse_dir / "run_log.csv",
    }
