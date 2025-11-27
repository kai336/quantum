import contextlib
import os
from typing import Iterable, List, Tuple

from throughput_sweep import SweepResult, run_single


def run_silent(params: dict) -> SweepResult:
    # run_singleから出る標準出力を捨てて静かに実行
    with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
        return run_single(**params, verbose_sim=False)


def sweep_p_swap(
    *,
    init_fidelity: float,
    p_values: Iterable[float],
    common_params: dict,
) -> List[SweepResult]:
    results: List[SweepResult] = []
    for p in p_values:
        params = common_params | {"p_swap": p, "init_fidelity": init_fidelity}
        results.append(run_silent(params))
    return results


def sweep_init_fidelity(
    *,
    p_swap: float,
    fidelities: Iterable[float],
    common_params: dict,
) -> List[SweepResult]:
    results: List[SweepResult] = []
    for fid in fidelities:
        params = common_params | {"p_swap": p_swap, "init_fidelity": fid}
        results.append(run_silent(params))
    return results


def plot_curve(
    xs: List[float],
    ys: List[float],
    xlabel: str,
    title: str,
    outfile: str,
):
    # 依存ライブラリなしで簡易SVGラインプロットを生成
    width, height = 640, 400
    margin = 60

    def scale(
        value: float, min_v: float, max_v: float, out_min: float, out_max: float
    ) -> float:
        if max_v == min_v:
            return (out_min + out_max) / 2
        ratio = (value - min_v) / (max_v - min_v)
        return out_min + ratio * (out_max - out_min)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    y_range = max_y - min_y
    if y_range == 0:
        min_y -= 0.001
        max_y += 0.001

    # 軸ライン
    x0, y0 = margin, height - margin
    x1, y1 = width - margin, margin

    # データ点
    points: List[Tuple[float, float]] = []
    for x, y in zip(xs, ys):
        px = scale(x, min_x, max_x, x0, x1)
        py = scale(y, min_y, max_y, y0, y1)
        points.append((px, py))

    polyline = " ".join(f"{px},{py}" for px, py in points)

    # 軸目盛（x方向は入力そのもの、y方向は2分割）
    y_ticks = [min_y, (min_y + max_y) / 2, max_y]
    x_ticks = xs

    def fmt(v: float) -> str:
        return f"{v:.3f}".rstrip("0").rstrip(".")

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<style>text{font-family:"DejaVu Sans",sans-serif;font-size:12px;}'
        "line{stroke:#333;stroke-width:1} "
        "polyline{fill:none;stroke:#1b73e8;stroke-width:2} "
        "circle{fill:#1b73e8}</style>",
        # 枠線
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" '
        'fill="white" stroke="#ccc" stroke-width="1"/>',
        # 軸
        f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" />',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" />',
    ]

    for yt in y_ticks:
        py = scale(yt, min_y, max_y, y0, y1)
        svg_lines.append(
            f'<line x1="{x0}" y1="{py}" x2="{x1}" y2="{py}" stroke="#ddd" />'
        )
        svg_lines.append(
            f'<text x="{x0-10}" y="{py+4}" text-anchor="end">{fmt(yt)}</text>'
        )

    for xt in x_ticks:
        px = scale(xt, min_x, max_x, x0, x1)
        svg_lines.append(
            f'<line x1="{px}" y1="{y0}" x2="{px}" y2="{y0-4}" stroke="#333" />'
        )
        svg_lines.append(
            f'<text x="{px}" y="{y0+18}" text-anchor="middle">{fmt(xt)}</text>'
        )

    svg_lines.append(f'<polyline points="{polyline}"/>')
    for px, py in points:
        svg_lines.append(f'<circle cx="{px}" cy="{py}" r="3"/>')

    svg_lines.append(
        f'<text x="{(x0+x1)/2}" y="{height-20}" text-anchor="middle">{xlabel}</text>'
    )
    svg_lines.append(
        f'<text x="{margin/2}" y="{(y0+y1)/2}" text-anchor="middle" '
        f'transform="rotate(-90 {margin/2},{(y0+y1)/2})">スループット（完了要求/タイムスロット）</text>'
    )
    svg_lines.append(
        f'<text x="{width/2}" y="{30}" text-anchor="middle" font-size="14">{title}</text>'
    )

    svg_lines.append("</svg>")

    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def main():
    common_params = {
        "nodes": 50,
        "requests": 5,
        "seed": 42,
        "sim_time": 10_000,
        "f_req": 0.8,
    }

    # 1) init_fidelity=0.8固定、p_swapを変化
    p_values = [0.2, 0.3, 0.4, 0.5, 0.6]
    res_p = sweep_p_swap(
        init_fidelity=0.8, p_values=p_values, common_params=common_params
    )
    throughput_p = [r.throughput for r in res_p]
    plot_curve(
        xs=p_values,
        ys=throughput_p,
        xlabel="p_swap",
        title="init_fidelity=0.8でのスループット",
        outfile="throughput_vs_p_swap.png",
    )

    # 2) p_swap=0.4固定、init_fidelityを変化
    fidelities = [0.8, 0.85, 0.9, 0.95]
    res_fid = sweep_init_fidelity(
        p_swap=0.4, fidelities=fidelities, common_params=common_params
    )
    throughput_fid = [r.throughput for r in res_fid]
    plot_curve(
        xs=fidelities,
        ys=throughput_fid,
        xlabel="init_fidelity",
        title="p_swap=0.4でのスループット",
        outfile="throughput_vs_init_fidelity.png",
    )

    print("==== init_fidelity=0.8 固定、p_swap掃引 ====")
    for r in res_p:
        print(
            f"p_swap={r.p_swap:.2f}, throughput={r.throughput:.6f}, "
            f"finished={r.finished}, avg_finish_slot={r.avg_finish_slot}"
        )

    print("==== p_swap=0.4 固定、init_fidelity掃引 ====")
    for r in res_fid:
        print(
            f"init_fidelity={r.init_fidelity:.2f}, throughput={r.throughput:.6f}, "
            f"finished={r.finished}, avg_finish_slot={r.avg_finish_slot}"
        )


if __name__ == "__main__":
    main()
