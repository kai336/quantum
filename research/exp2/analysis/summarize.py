"""summary.csvを集計してシナリオ単位の平均を出力する。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _to_float(value: str) -> float | None:
    if value == "" or value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str) -> int | None:
    if value == "" or value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes")


def _mean(values: Iterable[float]) -> float | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def load_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def aggregate(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    key_fields = [
        "scenario_id",
        "t_mem",
        "p_swap",
        "link_fidelity",
        "psw_threshold",
        "enable_psw",
    ]
    metrics = [
        "finished",
        "avg_wait",
        "p50_wait",
        "p90_wait",
        "throughput",
        "final_fidelity_mean",
        "final_fidelity_p10",
        "swap_wait_time_mean",
        "psw_attempts",
        "psw_success",
        "psw_fail",
        "psw_cancelled",
        "attempts_per_finished",
    ]

    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        if row.get("status") != "ok":
            continue
        scenario_id = row.get("scenario_id", "")
        enable_psw = row.get("enable_psw", "false")
        key = (scenario_id, enable_psw)
        buckets.setdefault(key, []).append(row)

    aggregated: List[Dict[str, Any]] = []
    for _, bucket in buckets.items():
        sample = bucket[0]
        agg_row: Dict[str, Any] = {}
        for field in key_fields:
            agg_row[field] = sample.get(field)
        for metric in metrics:
            values = [_to_float(r.get(metric, "")) for r in bucket]
            if metric in ("finished", "psw_attempts", "psw_success", "psw_fail", "psw_cancelled"):
                agg_row[metric] = int(sum(v for v in values if v is not None))
            else:
                agg_row[metric] = _mean([v for v in values if v is not None])
        aggregated.append(agg_row)

    # on/off差分
    index: Dict[str, Dict[bool, Dict[str, Any]]] = {}
    for row in aggregated:
        scenario_id = str(row.get("scenario_id"))
        enable_psw = _to_bool(row.get("enable_psw", "false"))
        index.setdefault(scenario_id, {})[enable_psw] = row

    delta_targets = [
        "finished",
        "avg_wait",
        "p50_wait",
        "p90_wait",
        "throughput",
        "final_fidelity_mean",
        "final_fidelity_p10",
        "swap_wait_time_mean",
        "attempts_per_finished",
    ]
    for bucket in index.values():
        row_off = bucket.get(False)
        row_on = bucket.get(True)
        if row_off is None or row_on is None:
            continue
        for metric in delta_targets:
            on_val = _to_float(row_on.get(metric, ""))
            off_val = _to_float(row_off.get(metric, ""))
            delta = None if on_val is None or off_val is None else on_val - off_val
            row_on[f"delta_{metric}"] = delta
            row_off[f"delta_{metric}"] = delta

    return aggregated


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="summary.csvのシナリオ集計")
    parser.add_argument("--input", required=True, help="summary.csvのパス")
    parser.add_argument(
        "--output", default=None, help="出力先(省略でsummary_agg.csv)"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name("summary_agg.csv")
    )

    rows = load_rows(input_path)
    agg_rows = aggregate(rows)
    write_csv(output_path, agg_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
