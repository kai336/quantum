import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from exp.run_dir import find_latest_run_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_NAME = "psw_tmem_sweep_long.csv"
OUT_WAIT_NAME = "psw_tmem_sweep_wait.png"
OUT_RATE_NAME = "psw_tmem_sweep_psw_rate.png"


@dataclass(frozen=True)
class Row:
    t_mem: float
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


def plot_wait(rows: list[Row], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    for mode, label, color, marker in [
        ("psw_on", "PSW enabled", "#1b73e8", "o"),
        ("psw_off", "PSW disabled", "#ef6c00", "s"),
    ]:
        sub = sorted([r for r in rows if r.mode == mode], key=lambda x: x.t_mem)
        xs = [r.t_mem for r in sub]
        ys = [
            r.avg_wait_per_request_slot
            if r.avg_wait_per_request_slot is not None
            else float("nan")
            for r in sub
        ]
        ax.plot(xs, ys, marker=marker, color=color, linewidth=2, label=label)

    ax.set_xscale("log")
    ax.set_title("Average wait per request vs memory lifetime (T_MEM)")
    ax.set_xlabel("Memory lifetime T_MEM (s, log scale)")
    ax.set_ylabel("Average wait (slots)")
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    ax.legend()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_psw_rate(rows: list[Row], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    sub = sorted([r for r in rows if r.mode == "psw_on"], key=lambda x: x.t_mem)
    xs = [r.t_mem for r in sub]
    ys = [
        r.psw_purify_attempts_per_finished
        if r.psw_purify_attempts_per_finished is not None
        else float("nan")
        for r in sub
    ]
    ax.plot(xs, ys, marker="o", color="#188038", linewidth=2)

    ax.set_xscale("log")
    ax.set_title("PSW purify attempts per finished request vs T_MEM")
    ax.set_xlabel("Memory lifetime T_MEM (s, log scale)")
    ax.set_ylabel("Attempts / finished request")
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot PSW T_MEM sweep results")
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Run directory containing psw_tmem_sweep_long.csv",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run_dir("psw_tmem_sweep")
    if run_dir is None:
        raise SystemExit("run_dir is not set and no matching run directory was found")
    data_path = run_dir / DATA_NAME
    out_wait = run_dir / OUT_WAIT_NAME
    out_rate = run_dir / OUT_RATE_NAME
    rows = load_rows(data_path)
    plot_wait(rows, out_wait)
    plot_psw_rate(rows, out_rate)
    print(f"Saved: {out_wait}")
    print(f"Saved: {out_rate}")


if __name__ == "__main__":
    main()
