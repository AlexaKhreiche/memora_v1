from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def latency_csv_path() -> Path:
    path = _project_root() / "data" / "latency_results.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def log_latency_row(row: Dict[str, Any]) -> None:
    path = latency_csv_path()

    fieldnames = [
        "trace_id",
        "event_type",
        "t_created",
        "t_published",
        "t_received",
        "t_finalized",
        "t_ui_written",
        "source_to_bus_delay",
        "bus_wait_delay",
        "brain_processing_delay",
        "ui_write_delay",
        "end_to_end_delay",
    ]

    file_exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k) for k in fieldnames})