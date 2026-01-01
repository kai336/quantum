import argparse
import csv
import sys
from pathlib import Path
from typing import List, TypedDict

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exp.run_dir import find_latest_run_dir


class Row(TypedDict):
    p_swap: float
    avg_time: float
    trial_count: int
    total_finished: int


def load_rows(path: str) -> List[Row]:
    """p_swap_throughput_sweep.csvを読み込んで数値型に変換する。"""
    rows: List[Row] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            avg_raw = r["avg_time_per_request_slot"]
            rows.append(
                Row(
                    p_swap=float(r["p_swap"]),
                    avg_time=float(avg_raw) if avg_raw else float("nan"),
                    trial_count=int(r["trial_count"]),
                    total_finished=int(r["total_finished"]),
                )
            )
    return rows


def plot(rows: List[Row], output: str) -> None:
    """平均リクエスト実行時間を英語ラベルでプロットして保存する。"""
    # p_swapでソートしてプロット
    rows_sorted = sorted(rows, key=lambda x: x["p_swap"])
    xs = [r["p_swap"] for r in rows_sorted]
    ys = [r["avg_time"] for r in rows_sorted]

    plt.figure(figsize=(6.4, 4))
    plt.plot(xs, ys, marker="o", color="#1b73e8", linewidth=2)
    plt.xlabel("p_swap")
    plt.ylabel("Average completion time per request (time slots)")
    plt.title("Average completion time vs p_swap")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output, dpi=150)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot average request time vs p_swap")
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Run directory containing p_swap_sweep.csv",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run_dir("p_swap_sweep")
    if run_dir is None:
        raise SystemExit("run_dir is not set and no matching run directory was found")
    csv_path = run_dir / "p_swap_sweep.csv"
    output_path = run_dir / "avg_request_time_vs_p_swap.png"
    rows = load_rows(str(csv_path))
    if not rows:
        raise SystemExit(f"CSV is empty: {csv_path}")
    plot(rows, str(output_path))
    print(f"Saved plot: {output_path}")


if __name__ == "__main__":
    main()
