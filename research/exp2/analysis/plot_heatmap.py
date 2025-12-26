"""summary.csvからヒートマップを生成する。"""

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


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description="PSW差分ヒートマップ")
    parser.add_argument("--input", required=True, help="summary.csvのパス")
    parser.add_argument("--output", required=True, help="出力PNG")
    parser.add_argument(
        "--metric",
        default="delta_avg_wait",
        help="プロットする指標(例: delta_avg_wait)",
    )
    parser.add_argument("--link-fidelity", type=float, default=None)
    parser.add_argument("--psw-threshold", type=float, default=None)
    args = parser.parse_args()

    rows = [r for r in load_rows(Path(args.input)) if r.get("status") == "ok"]
    rows = [r for r in rows if _to_bool(r.get("enable_psw", "false"))]

    if args.link_fidelity is not None:
        rows = [
            r
            for r in rows
            if _to_float(r.get("link_fidelity", "")) == args.link_fidelity
        ]
    if args.psw_threshold is not None:
        rows = [
            r
            for r in rows
            if _to_float(r.get("psw_threshold", "")) == args.psw_threshold
        ]

    points: Dict[Tuple[float, float], List[float]] = {}
    for row in rows:
        t_mem = _to_float(row.get("t_mem", ""))
        p_swap = _to_float(row.get("p_swap", ""))
        metric = _to_float(row.get(args.metric, ""))
        if t_mem is None or p_swap is None or metric is None:
            continue
        points.setdefault((t_mem, p_swap), []).append(metric)

    if not points:
        return 0

    unique_t = sorted({k[0] for k in points})
    unique_p = sorted({k[1] for k in points})

    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(7, 4))
    if len(unique_t) > 1 and len(unique_p) > 1:
        grid = np.full((len(unique_t), len(unique_p)), float("nan"))
        for i, t_mem in enumerate(unique_t):
            for j, p_swap in enumerate(unique_p):
                vals = points.get((t_mem, p_swap))
                if vals:
                    grid[i, j] = sum(vals) / len(vals)
        im = ax.imshow(grid, origin="lower", aspect="auto")
        ax.set_xticks(range(len(unique_p)), [str(v) for v in unique_p])
        ax.set_yticks(range(len(unique_t)), [str(v) for v in unique_t])
        ax.set_xlabel("p_swap")
        ax.set_ylabel("t_mem")
        fig.colorbar(im, ax=ax, label=args.metric)
    else:
        xs = [k[0] for k in points]
        ys = [sum(points[k]) / len(points[k]) for k in points]
        ax.plot(xs, ys, marker="o", linestyle="-")
        ax.set_xlabel("t_mem")
        ax.set_ylabel(args.metric)

    ax.set_title(f"PSW差分ヒートマップ: {args.metric}")
    fig.tight_layout()
    fig.savefig(Path(args.output))
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
