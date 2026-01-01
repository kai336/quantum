import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXP_DIR = ROOT / "exp"
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

from run_dir import find_latest_run_dir

DATA_NAME = "psw_onoff_compare_long.csv"
OUT_NAME = "psw_onoff_compare_wait.png"


@dataclass(frozen=True)
class Row:
    mode: str
    avg_wait_per_request_slot: float | None
    total_finished: int
    t_mem: float
    p_swap: float
    psw_threshold: float
    init_fidelity: float


def _parse_optional_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def load_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                Row(
                    mode=r["mode"],
                    avg_wait_per_request_slot=_parse_optional_float(
                        r.get("avg_wait_per_request_slot", "")
                    ),
                    total_finished=int(r.get("total_finished", 0)),
                    t_mem=float(r["t_mem"]),
                    p_swap=float(r["p_swap"]),
                    psw_threshold=float(r["psw_threshold"]),
                    init_fidelity=float(r["init_fidelity"]),
                )
            )
    return rows


def plot_wait(rows: list[Row], out_path: Path) -> None:
    if not rows:
        raise SystemExit("no rows to plot")
    sample = rows[0]
    order = ["psw_off", "psw_on"]
    labels = {"psw_off": "PSW off", "psw_on": "PSW on"}
    colors = {"psw_off": "#ef6c00", "psw_on": "#1b73e8"}

    values = []
    finished = []
    for mode in order:
        row = next((r for r in rows if r.mode == mode), None)
        values.append(
            row.avg_wait_per_request_slot if row and row.avg_wait_per_request_slot is not None else float("nan")
        )
        finished.append(row.total_finished if row else 0)

    fig, ax = plt.subplots(figsize=(6, 4))
    xs = range(len(order))
    ax.bar(xs, values, color=[colors[m] for m in order])
    ax.set_xticks(list(xs), [labels[m] for m in order])
    ax.set_ylabel("Average wait (slots)")
    ax.set_title(
        "PSW on/off average wait\n"
        f"T_MEM={sample.t_mem}, p_swap={sample.p_swap}, init={sample.init_fidelity}, "
        f"threshold={sample.psw_threshold}"
    )
    for idx, val in enumerate(values):
        if val != val:
            continue
        ax.text(
            idx,
            val,
            f"{val:.1f}\n(n={finished[idx]})",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.grid(True, axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot PSW on/off comparison results")
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Run directory containing psw_onoff_compare_long.csv",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run_dir("psw_onoff_compare")
    if run_dir is None:
        raise SystemExit("run_dir is not set and no matching run directory was found")
    data_path = run_dir / DATA_NAME
    out_path = run_dir / OUT_NAME
    rows = load_rows(data_path)
    plot_wait(rows, out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
