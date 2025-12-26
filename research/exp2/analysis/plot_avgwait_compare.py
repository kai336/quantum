"""PSW on/offのavg_wait比較プロットを作成する。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple


def _to_float(value: str) -> float | None:
    if value == "" or value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes")


def _exp_name_from_dir(path: Path) -> str | None:
    parts = path.name.split("_", 2)
    if len(parts) < 3:
        return None
    return parts[2]


def _load_summary(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def collect_points(results_root: Path, exp_prefix: str) -> List[Tuple[float, float | None, float | None]]:
    points: List[Tuple[float, float | None, float | None]] = []
    for run_dir in sorted(results_root.iterdir()):
        if not run_dir.is_dir():
            continue
        exp_name = _exp_name_from_dir(run_dir)
        if exp_name is None or not exp_name.startswith(exp_prefix):
            continue
        summary_path = run_dir / "summary.csv"
        if not summary_path.exists():
            continue
        rows = [r for r in _load_summary(summary_path) if r.get("status") == "ok"]
        if not rows:
            continue
        t_vals = {r.get("t_mem") for r in rows if r.get("t_mem") not in (None, "")}
        if len(t_vals) != 1:
            continue
        t_mem = _to_float(next(iter(t_vals)))
        if t_mem is None:
            continue

        on_vals = [
            _to_float(r.get("avg_wait", ""))
            for r in rows
            if _to_bool(r.get("enable_psw", "false"))
        ]
        off_vals = [
            _to_float(r.get("avg_wait", ""))
            for r in rows
            if not _to_bool(r.get("enable_psw", "false"))
        ]
        avg_on = sum(v for v in on_vals if v is not None) / len(on_vals) if on_vals else None
        avg_off = sum(v for v in off_vals if v is not None) / len(off_vals) if off_vals else None
        points.append((t_mem, avg_on, avg_off))

    points.sort(key=lambda x: x[0])
    return points


def main() -> int:
    parser = argparse.ArgumentParser(description="avg_waitのPSW on/off比較プロット")
    parser.add_argument("--results-root", required=True, help="resultsディレクトリ")
    parser.add_argument("--exp-prefix", required=True, help="exp_nameの接頭辞")
    parser.add_argument("--output", required=True, help="出力PNG")
    args = parser.parse_args()

    points = collect_points(Path(args.results_root), args.exp_prefix)
    if not points:
        return 0

    xs = [p[0] for p in points]
    ys_on = [p[1] for p in points]
    ys_off = [p[2] for p in points]

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(xs, ys_off, marker="o", linestyle="-", label="avg_wait_psw_off")
    ax.plot(xs, ys_on, marker="o", linestyle="-", label="avg_wait_psw_on")
    ax.set_xlabel("t_mem")
    ax.set_ylabel("avg_wait")
    ax.set_title("avg_wait comparison (PSW on/off)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(Path(args.output))
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
