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


def _filter_by_psw(rows: List[Dict[str, str]], enable_psw: str) -> List[Dict[str, str]]:
    if enable_psw == "all":
        return rows
    want_on = enable_psw == "on"
    return [r for r in rows if _to_bool(r.get("enable_psw", "false")) == want_on]


def _average_points(
    rows: List[Dict[str, str]],
    metric: str,
) -> Dict[Tuple[float, float], List[float]]:
    points: Dict[Tuple[float, float], List[float]] = {}
    for row in rows:
        t_mem = _to_float(row.get("t_mem", ""))
        p_swap = _to_float(row.get("p_swap", ""))
        value = _to_float(row.get(metric, ""))
        if t_mem is None or p_swap is None or value is None:
            continue
        points.setdefault((t_mem, p_swap), []).append(value)
    return points


def _draw_single(ax, points: Dict[Tuple[float, float], List[float]], metric: str) -> None:
    import numpy as np

    if not points:
        return
    unique_t = sorted({k[0] for k in points})
    unique_p = sorted({k[1] for k in points})

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
        ax.figure.colorbar(im, ax=ax, label=metric)
    else:
        xs = [k[0] for k in points]
        ys = [sum(points[k]) / len(points[k]) for k in points]
        ax.plot(xs, ys, marker="o", linestyle="-")
        ax.set_xlabel("t_mem")
        ax.set_ylabel(metric)


def main() -> int:
    parser = argparse.ArgumentParser(description="PSW on/offの指標ヒートマップ")
    parser.add_argument("--input", required=True, help="summary.csvのパス")
    parser.add_argument("--output", required=True, help="出力PNG")
    parser.add_argument(
        "--metric",
        default="avg_wait",
        help="プロットする指標(例: avg_wait)",
    )
    parser.add_argument(
        "--enable-psw",
        choices=["on", "off", "all"],
        default="on",
        help="PSWの有効/無効をフィルタ（bothの比較は--compare-onoffを使用）",
    )
    parser.add_argument(
        "--compare-onoff",
        action="store_true",
        default=True,
        help="PSW on/offそれぞれの平均値を並べて出力する（デフォルトで有効）",
    )
    parser.add_argument("--link-fidelity", type=float, default=None)
    parser.add_argument("--psw-threshold", type=float, default=None)
    args = parser.parse_args()

    rows = [r for r in load_rows(Path(args.input)) if r.get("status") == "ok"]

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

    if args.compare_onoff:
        rows_on = _filter_by_psw(rows, "on")
        rows_off = _filter_by_psw(rows, "off")
        points_on = _average_points(rows_on, args.metric)
        points_off = _average_points(rows_off, args.metric)
        if not points_on and not points_off:
            return 0

        from matplotlib.colors import Normalize
        import matplotlib.pyplot as plt
        import numpy as np

        mean_on = {k: sum(v) / len(v) for k, v in points_on.items()}
        mean_off = {k: sum(v) / len(v) for k, v in points_off.items()}
        all_vals = list(mean_on.values()) + list(mean_off.values())
        if not all_vals:
            return 0

        unique_t = sorted({k[0] for k in mean_on.keys() | mean_off.keys()})
        unique_p = sorted({k[1] for k in mean_on.keys() | mean_off.keys()})

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.set_title(f"PSW on/off 平均: {args.metric}")

        if len(unique_t) > 1 and len(unique_p) == 1:
            p = unique_p[0]
            xs = unique_t
            ys_on = [mean_on.get((t, p)) for t in xs]
            ys_off = [mean_off.get((t, p)) for t in xs]
            if any(v is not None for v in ys_off):
                ax.plot(xs, ys_off, marker="o", linestyle="-", label="PSW off", color="tab:blue")
            if any(v is not None for v in ys_on):
                ax.plot(xs, ys_on, marker="o", linestyle="-", label="PSW on", color="tab:orange")
            ax.set_xlabel("t_mem")
            ax.set_ylabel(args.metric)
        elif len(unique_p) > 1 and len(unique_t) == 1:
            t = unique_t[0]
            xs = unique_p
            ys_on = [mean_on.get((t, p)) for p in xs]
            ys_off = [mean_off.get((t, p)) for p in xs]
            if any(v is not None for v in ys_off):
                ax.plot(xs, ys_off, marker="o", linestyle="-", label="PSW off", color="tab:blue")
            if any(v is not None for v in ys_on):
                ax.plot(xs, ys_on, marker="o", linestyle="-", label="PSW on", color="tab:orange")
            ax.set_xlabel("p_swap")
            ax.set_ylabel(args.metric)
        else:
            norm = Normalize(vmin=min(all_vals), vmax=max(all_vals) if max(all_vals) > min(all_vals) else min(all_vals) + 1e-9)
            xs_on = [k[1] for k in mean_on.keys()]
            ys_on = [k[0] for k in mean_on.keys()]
            cs_on = [mean_on[k] for k in mean_on.keys()]
            xs_off = [k[1] for k in mean_off.keys()]
            ys_off = [k[0] for k in mean_off.keys()]
            cs_off = [mean_off[k] for k in mean_off.keys()]
            scat_off = ax.scatter(xs_off, ys_off, c=cs_off, cmap="Blues", norm=norm, marker="s", label="PSW off")
            scat_on = ax.scatter(xs_on, ys_on, c=cs_on, cmap="Oranges", norm=norm, marker="o", label="PSW on")
            ax.set_xlabel("p_swap")
            ax.set_ylabel("t_mem")
            cbar = fig.colorbar(scat_on if cs_on else scat_off, ax=ax)
            cbar.set_label(args.metric)

        ax.legend()
        fig.tight_layout()
        fig.savefig(Path(args.output))
        plt.close(fig)
        return 0

    rows = _filter_by_psw(rows, args.enable_psw)
    points = _average_points(rows, args.metric)
    if not points:
        return 0

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    _draw_single(ax, points, args.metric)
    ax.set_title(f"PSWヒートマップ: {args.metric} (enable_psw={args.enable_psw})")
    fig.tight_layout()
    fig.savefig(Path(args.output))
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
