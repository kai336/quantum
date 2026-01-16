"""summary.csvからPSW on/offの平均待ち時間グラフを生成するスクリプト。"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "out"
# 手動で特定のsummary.csvを使いたい場合はここにパスを設定する
SUMMARY_PATH: str | None = None
# 出力先ディレクトリを固定したい場合はここに設定する（既存ディレクトリ不可）
OUT_DIR: str | None = None


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
    if not grouped:
        raise SystemExit("平均待ち時間の有効なデータがありませんでした。")

    t_list = sorted(grouped.keys())
    ys_on = [_mean(grouped[t][True]) for t in t_list]
    ys_off = [_mean(grouped[t][False]) for t in t_list]

    fig, ax = plt.subplots(figsize=(8, 4))
    x = list(range(len(t_list)))
    ax.plot(
        x,
        [y if y is not None else math.nan for y in ys_off],
        marker="o",
        label="PSW off",
    )
    ax.plot(
        x,
        [y if y is not None else math.nan for y in ys_on],
        marker="o",
        label="PSW on",
    )
    ax.set_xticks(x)
    ax.set_xticklabels([f"{t:g}" for t in t_list])
    ax.set_xlabel("t_mem")
    ax.set_ylabel("avg_wait (slots)")
    ax.set_title("PSW on/off avg_wait")
    ax.legend()
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


def _resolve_out_dir(out_dir: str | None) -> Path:
    if out_dir:
        base = Path(out_dir).resolve()
    else:
        base = (OUT_ROOT / f"{datetime.now():%Y%m%d_%H%M%S}_avg_wait_plot").resolve()
    if OUT_ROOT not in base.parents:
        raise SystemExit(f"出力先は {OUT_ROOT} 配下にしてください: {base}")
    if base.exists():
        raise SystemExit(f"出力先が既に存在します: {base}")
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

    out_dir = _resolve_out_dir(OUT_DIR)
    out_png = out_dir / "avg_wait_onoff.png"
    plot_avg_wait(rows, out_png)
    print(f"Saved: {out_png}")


if __name__ == "__main__":
    main()
