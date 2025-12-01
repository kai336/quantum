import contextlib
import os
import sys
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt

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
    # matplotlibで折れ線グラフを保存
    plt.figure(figsize=(6.4, 4))
    plt.plot(xs, ys, marker="o", color="#1b73e8", linewidth=2)
    plt.xlabel(xlabel)
    plt.ylabel("Throughput (completed requests/time slot)")
    plt.title(title)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()


def main():
    common_params = {
        "nodes": 50,
        "requests": 5,
        "seed": 42,
        "sim_time": 10_000,
        "f_req": 0.8,
    }
    os.makedirs("data", exist_ok=True)

    # 1) init_fidelity=0.9固定、p_swapを変化
    p_values = [0.2, 0.3, 0.4, 0.5, 0.6]
    res_p = sweep_p_swap(
        init_fidelity=0.9, p_values=p_values, common_params=common_params
    )
    throughput_p = [r.throughput for r in res_p]
    plot_curve(
        xs=p_values,
        ys=throughput_p,
        xlabel="p_swap",
        title="Throughput at init_fidelity=0.9",
        outfile=os.path.join("data", "throughput_vs_p_swap.png"),
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
        title="Throughput at p_swap=0.4",
        outfile=os.path.join("data", "throughput_vs_init_fidelity.png"),
    )

    print("==== init_fidelity=0.9 固定、p_swap掃引 ====")
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
