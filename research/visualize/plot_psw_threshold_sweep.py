import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from exp.run_dir import find_latest_run_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_NAME = "psw_threshold_sweep_long.csv"
OUT_WAIT_NAME = "psw_threshold_sweep_wait.png"
OUT_RATE_NAME = "psw_threshold_sweep_psw_rate.png"


@dataclass(frozen=True)
class Row:
    t_mem: float
    psw_threshold: float
    p_swap: float
    mode: str
    avg_wait_per_request_slot: float | None
    psw_purify_attempts_per_finished: float | None


def _parse_optional_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    return float(s)


def load_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                Row(
                    t_mem=float(r["t_mem"]),
                    psw_threshold=float(r["psw_threshold"]),
                    p_swap=float(r["p_swap"]),
                    mode=r["mode"],
                    avg_wait_per_request_slot=_parse_optional_float(
                        r.get("avg_wait_per_request_slot", "")
                    ),
                    psw_purify_attempts_per_finished=_parse_optional_float(
                        r.get("psw_purify_attempts_per_finished", "")
                    ),
                )
            )
    return rows


def _group_thresholds(rows: list[Row]) -> list[float]:
    return sorted({r.psw_threshold for r in rows})


def plot_wait_by_threshold(rows: list[Row], out_path: Path) -> None:
    thresholds = _group_thresholds(rows)
    if not thresholds:
        raise ValueError("no thresholds found")

    n = len(thresholds)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(8, max(3.4, 2.8 * n)), sharex=True)
    if n == 1:
        axes = [axes]

    for ax, thr in zip(axes, thresholds):
        sub = [r for r in rows if r.psw_threshold == thr]
        for mode, label, color, marker in [
            ("psw_on", "PSW enabled", "#1b73e8", "o"),
            ("psw_off", "PSW disabled", "#ef6c00", "s"),
        ]:
            ms = sorted([r for r in sub if r.mode == mode], key=lambda x: x.p_swap)
            xs = [r.p_swap for r in ms]
            ys = [
                r.avg_wait_per_request_slot
                if r.avg_wait_per_request_slot is not None
                else float("nan")
                for r in ms
            ]
            ax.plot(xs, ys, marker=marker, color=color, linewidth=2, label=label)

        ax.set_title(f"Average wait per request (threshold={thr:g})")
        ax.set_ylabel("Average wait (slots)")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend()

    axes[-1].set_xlabel("Swap success probability (p_swap)")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_psw_rate(rows: list[Row], out_path: Path) -> None:
    thresholds = _group_thresholds(rows)
    if not thresholds:
        raise ValueError("no thresholds found")

    n = len(thresholds)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(8, max(3.2, 2.6 * n)), sharex=True)
    if n == 1:
        axes = [axes]

    for ax, thr in zip(axes, thresholds):
        sub = sorted(
            [r for r in rows if r.psw_threshold == thr and r.mode == "psw_on"],
            key=lambda x: x.p_swap,
        )
        xs = [r.p_swap for r in sub]
        ys = [
            r.psw_purify_attempts_per_finished
            if r.psw_purify_attempts_per_finished is not None
            else float("nan")
            for r in sub
        ]
        ax.plot(xs, ys, marker="o", color="#188038", linewidth=2)
        ax.set_title(f"PSW purify attempts per finished request (threshold={thr:g})")
        ax.set_ylabel("Attempts / finished request")
        ax.grid(True, linestyle="--", alpha=0.5)

    axes[-1].set_xlabel("Swap success probability (p_swap)")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot PSW threshold sweep results")
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Run directory containing psw_threshold_sweep_long.csv",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run_dir("psw_threshold_sweep")
    if run_dir is None:
        raise SystemExit("run_dir is not set and no matching run directory was found")
    data_path = run_dir / DATA_NAME
    out_wait = run_dir / OUT_WAIT_NAME
    out_rate = run_dir / OUT_RATE_NAME
    rows = load_rows(data_path)
    plot_wait_by_threshold(rows, out_wait)
    plot_psw_rate(rows, out_rate)
    print(f"Saved: {out_wait}")
    print(f"Saved: {out_rate}")


if __name__ == "__main__":
    main()
