import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "swap_waiting_results.csv"
OUTPUT_PATH = Path(__file__).with_name("swap_waiting.png")


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
    p_swap, avg_swap_wait, avg_request_wait = load_results(DATA_PATH)
    plot_swap_waiting(p_swap, avg_swap_wait, avg_request_wait, OUTPUT_PATH)
    print(f"Saved plot to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
