"""summary.csvからPSW on/offの平均待ち時間グラフを生成するスクリプト。"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

import japanize_matplotlib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
# 手動で特定のsummary.csvを使いたい場合はここにパスを設定する
SUMMARY_PATH: str | None = (
    "/home/kai/quantum/research/manual_exp/out/20260108_012917_t_mem sweep 1-5sec/summary.csv"
)
# 出力先ディレクトリを固定したい場合はここに設定する（既存ディレクトリ不可）
OUT_DIR: str = "/home/kai/quantum/research/manual_exp/plots"
SLOTS_PER_SEC = 3000.0


@dataclass(frozen=True)
class SummaryRow:
    t_mem: float
    enable_psw: bool
    avg_wait: float | None
    status: str
    meta: Mapping[str, float | None]


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _parse_optional_float(value: str | None) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def load_summary(path: Path) -> list[SummaryRow]:
    rows: list[SummaryRow] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                SummaryRow(
                    t_mem=float(r["t_mem"]),
                    enable_psw=_parse_bool(r["enable_psw"]),
                    avg_wait=_parse_optional_float(r.get("avg_wait")),
                    status=(r.get("status") or "").strip() or "ok",
                    meta={
                        "p_swap": _parse_optional_float(r.get("p_swap")),
                        "psw_threshold": _parse_optional_float(r.get("psw_threshold")),
                        "link_fidelity": _parse_optional_float(r.get("link_fidelity")),
                    },
                )
            )
    return rows


def _mean(values: Iterable[float]) -> float | None:
    xs = list(values)
    if not xs:
        return None
    return sum(xs) / len(xs)


def _group_avg_wait(rows: list[SummaryRow]) -> dict[float, dict[bool, list[float]]]:
    grouped: dict[float, dict[bool, list[float]]] = {}
    for row in rows:
        if row.status != "ok" or row.avg_wait is None:
            continue
        grouped.setdefault(row.t_mem, {True: [], False: []})
        grouped[row.t_mem][row.enable_psw].append(row.avg_wait)
    return grouped


def plot_avg_wait(rows: list[SummaryRow], out_png: Path) -> None:
    grouped = _group_avg_wait(rows)
    plt.rcParams.update(
        {
            "font.size": 15,
            "lines.linewidth": 2.0,
        }
    )
    t_list = sorted(grouped.keys())
    ys_on = [_mean(grouped[t][True]) for t in t_list]
    ys_off = [_mean(grouped[t][False]) for t in t_list]
    ys_off = [(y / SLOTS_PER_SEC) if y is not None else None for y in ys_off]
    ys_on = [(y / SLOTS_PER_SEC) if y is not None else None for y in ys_on]
    fig, ax = plt.subplots(figsize=(8, 4))
    x = list(range(len(t_list)))
    ax.plot(
        x,
        [y if y is not None else math.nan for y in ys_off],
        marker="x",
        label="PSW off",
        markersize=10,
    )
    ax.plot(
        x,
        [y if y is not None else math.nan for y in ys_on],
        marker="o",
        label="PSW on",
    )
    ax.set_ylim(bottom=0)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{t:g}" for t in t_list])
    ax.set_xlabel("メモリ保持時間 (s)")
    ax.set_ylabel("平均完了時間 (s)")
    ax.legend()
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png.with_suffix(".pdf"))
    plt.close(fig)


def _resolve_out_dir(out_dir: str | None) -> Path:
    if out_dir:
        base = Path(out_dir).resolve()
    base.mkdir(parents=True, exist_ok=False)
    return base


def _find_latest_summary(base_dir: Path) -> Path:
    candidates: list[tuple[float, Path]] = []
    for summary in base_dir.glob("*/summary.csv"):
        try:
            mtime = summary.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, summary))
    if not candidates:
        raise SystemExit(f"summary.csvが見つかりませんでした: {base_dir}配下")
    return max(candidates, key=lambda x: x[0])[1]


def main() -> None:
    if SUMMARY_PATH:
        summary_path = Path(SUMMARY_PATH).resolve()
    else:
        summary_path = _find_latest_summary(ROOT.parent / "manual_exp" / "out")

    if not summary_path.is_file():
        raise SystemExit(f"summary.csvが見つかりません: {summary_path}")
    rows = load_summary(summary_path)

    out_dir = Path(OUT_DIR)
    out_png = out_dir / "avg_waitv2.png"
    plot_avg_wait(rows, out_png)
    print(f"Saved: {out_png}")


if __name__ == "__main__":
    main()
