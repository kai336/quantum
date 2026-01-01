"""PSW on/offの平均待ち時間を棒グラフで比較する。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt


def _to_float(value: str | None) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_bool(value: str | None) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes")


def _load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)]


def _single_value(rows: List[Dict[str, str]], key: str) -> str:
    vals = {r.get(key, "") for r in rows if r.get(key, "") != ""}
    return vals.pop() if len(vals) == 1 else "/"


def main() -> int:
    parser = argparse.ArgumentParser(description="PSW on/off平均待ち時間の棒グラフを描画")
    parser.add_argument("--input", required=True, help="summary.csvのパス")
    parser.add_argument("--output", required=True, help="出力PNGパス")
    parser.add_argument("--metric", default="avg_wait", help="比較する指標（デフォルト: avg_wait）")
    parser.add_argument("--figsize", type=float, nargs=2, default=(12, 8), help="図サイズ (インチ)")
    args = parser.parse_args()

    rows = [r for r in _load_rows(Path(args.input)) if r.get("status") == "ok"]
    if not rows:
        return 0

    on_vals = [_to_float(r.get(args.metric)) for r in rows if _to_bool(r.get("enable_psw"))]
    off_vals = [_to_float(r.get(args.metric)) for r in rows if not _to_bool(r.get("enable_psw"))]
    on_vals = [v for v in on_vals if v is not None]
    off_vals = [v for v in off_vals if v is not None]

    if not on_vals and not off_vals:
        return 0

    mean_on = sum(on_vals) / len(on_vals) if on_vals else None
    mean_off = sum(off_vals) / len(off_vals) if off_vals else None

    fig, ax = plt.subplots(figsize=tuple(args.figsize))
    labels = []
    heights = []
    colors = []
    annot: List[Tuple[float, str]] = []

    if mean_off is not None:
        labels.append("PSW off")
        heights.append(mean_off)
        colors.append("#f27b00")
        annot.append((mean_off, f"{mean_off:.1f}\n(n={len(off_vals)})"))
    if mean_on is not None:
        labels.append("PSW on")
        heights.append(mean_on)
        colors.append("#1f78ff")
        annot.append((mean_on, f"{mean_on:.1f}\n(n={len(on_vals)})"))

    bars = ax.bar(labels, heights, color=colors)
    for bar, text in zip(bars, annot):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() * 1.01,
            text[1],
            ha="center",
            va="bottom",
            fontsize=12,
        )

    t_mem = _single_value(rows, "t_mem")
    p_swap = _single_value(rows, "p_swap")
    init_fid = _single_value(rows, "init_fidelity")
    psw_th = _single_value(rows, "psw_threshold")

    ax.set_ylabel(f"Average {args.metric} (slots)")
    ax.set_title(
        f"PSW on/off average {args.metric}\n"
        f"T_MEM={t_mem}, p_swap={p_swap}, init={init_fid}, threshold={psw_th}",
        fontsize=16,
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(Path(args.output))
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
