import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from exp.run_dir import find_latest_run_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_NAME = "swap_waiting.csv"
OUTPUT_NAME = "swap_waiting.png"


def load_results(path: Path):
    p_swap = []
    avg_swap_wait = []
    avg_request_wait = []

    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_swap.append(float(row["p_swap"]))
            avg_swap_wait.append(float(row["avg_wait_per_swap_slot"]))
            avg_request_wait.append(float(row["avg_wait_per_request_slot"]))

    return p_swap, avg_swap_wait, avg_request_wait


def plot_swap_waiting(p_swap, avg_swap_wait, avg_request_wait, dest: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(
        p_swap,
        avg_swap_wait,
        marker="o",
        label="Average wait per swap (slots)",
    )
    ax.plot(
        p_swap,
        avg_request_wait,
        marker="s",
        label="Average wait per request (slots)",
    )

    ax.set_title("Swap Waiting vs Swap Success Probability")
    ax.set_xlabel("Swap success probability (p_swap)")
    ax.set_ylabel("Average waiting time (slots)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend()
    fig.tight_layout()

    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=200)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot swap waiting results")
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Run directory containing swap_waiting.csv",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run_dir("swap_waiting")
    if run_dir is None:
        raise SystemExit("run_dir is not set and no matching run directory was found")
    data_path = run_dir / DATA_NAME
    output_path = run_dir / OUTPUT_NAME
    p_swap, avg_swap_wait, avg_request_wait = load_results(data_path)
    plot_swap_waiting(p_swap, avg_swap_wait, avg_request_wait, output_path)
    print(f"Saved plot to {output_path}")


if __name__ == "__main__":
    main()
