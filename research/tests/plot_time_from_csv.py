import csv
from typing import List, TypedDict

import matplotlib.pyplot as plt


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
    csv_path = "data/p_swap_throughput_sweep.csv"
    output_path = "data/avg_request_time_vs_p_swap.png"
    rows = load_rows(csv_path)
    if not rows:
        raise SystemExit(f"CSV is empty: {csv_path}")
    plot(rows, output_path)
    print(f"Saved plot: {output_path}")


if __name__ == "__main__":
    main()
