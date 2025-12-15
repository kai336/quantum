import argparse
import contextlib
import logging
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import matplotlib.pyplot as plt
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import qns.utils.log as log
from edp.app.controller_app import ControllerApp
from edp.app.node_app import NodeApp
from edp.sim import SIMULATOR_ACCURACY
from qns.entity.node import QNode
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology import WaxmanTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed


@dataclass
class RunFidelity:
    seed: int
    fidelities: List[float]
    finished: int
    requests: int


@dataclass
class FidelitySummary:
    p_swap: float
    init_fidelity: float
    avg_fidelity: float | None
    min_fidelity: float | None
    max_fidelity: float | None
    completion_rate: float
    total_finished: int
    trial_count: int


def parse_float_list(values: str) -> List[float]:
    return [float(v.strip()) for v in values.split(",") if v.strip()]


def parse_int_list(values: str) -> List[int]:
    return [int(v.strip()) for v in values.split(",") if v.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="最終的なもつれ忠実度を指標にしたバッチ実験"
    )
    parser.add_argument(
        "--p-swap-values",
        type=parse_float_list,
        default=[0.2, 0.4, 0.6],
        help="p_swap の候補 (カンマ区切り)",
    )
    parser.add_argument(
        "--init-fidelities",
        type=parse_float_list,
        default=[0.99],
        help="init_fidelity の候補 (カンマ区切り, デフォルトは0.99のみ)",
    )
    parser.add_argument("--nodes", type=int, default=50, help="Waxman のノード数")
    parser.add_argument("--requests", type=int, default=5, help="要求数")
    parser.add_argument("--sim-time", type=float, default=100_000, help="終了時刻")
    parser.add_argument(
        "--f-req", type=float, default=0.8, help="最小要求忠実度(f_req)"
    )
    parser.add_argument(
        "--seeds",
        type=parse_int_list,
        default=[42, 43, 44],
        help="シードのリスト (カンマ区切り)",
    )
    parser.add_argument(
        "--runs-per-seed", type=int, default=2, help="各シードでの繰り返し回数"
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO", help="ログレベル (DEBUG など)"
    )
    parser.add_argument(
        "--verbose-sim",
        action="store_true",
        help="シミュレーションの標準出力を抑制しない",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/final_fidelity_summary.csv",
        help="結果を書き出すCSVパス",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="集計後にヒートマップを生成する",
    )
    parser.add_argument(
        "--plot-path",
        type=str,
        default="data/final_fidelity_heatmap.png",
        help="ヒートマップの出力先",
    )
    return parser.parse_args()


def run_single(
    *,
    nodes: int,
    requests: int,
    seed: int,
    sim_time: float,
    f_req: float,
    p_swap: float,
    init_fidelity: float,
    verbose_sim: bool,
) -> RunFidelity:
    """単発シミュレーションで最終忠実度を収集する。"""
    memory_capacity = 5
    gen_rate = 50
    waxman_size = 1000
    waxman_alpha = 0.2
    waxman_beta = 0.6

    s = Simulator(0, sim_time, SIMULATOR_ACCURACY)
    set_seed(seed)

    topo = WaxmanTopology(
        nodes_number=nodes,
        size=waxman_size,
        alpha=waxman_alpha,
        beta=waxman_beta,
        nodes_apps=[
            NodeApp(
                p_swap=p_swap,
                gen_rate=gen_rate,
                memory_capacity=memory_capacity,
            )
        ],
    )
    net = QuantumNetwork(
        topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm()
    )

    net.build_route()
    net.random_requests(number=requests)

    controller_node = QNode(
        name="controller",
        apps=[
            ControllerApp(
                p_swap=p_swap,
                f_req=f_req,
                gen_rate=gen_rate,
                init_fidelity=init_fidelity,
            )
        ],
    )
    net.add_node(controller_node)

    net.install(s)
    net.build_route()
    if net.requests:
        net.query_route(net.requests[0].src, net.requests[0].dest)

    if verbose_sim:
        s.run()
    else:
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            s.run()

    controller_app = controller_node.apps[0]
    fidelities = [r["fidelity"] for r in controller_app.completed_requests]
    return RunFidelity(
        seed=seed,
        fidelities=fidelities,
        finished=len(fidelities),
        requests=requests,
    )


def run_batch(
    *,
    seeds: Iterable[int],
    runs_per_seed: int,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    p_swap: float,
    init_fidelity: float,
    verbose_sim: bool,
) -> List[RunFidelity]:
    """同一条件で複数回実行し忠実度サンプルを増やす。"""
    batch_results: List[RunFidelity] = []
    for base_seed in seeds:
        for rep in range(runs_per_seed):
            effective_seed = base_seed + rep
            batch_results.append(
                run_single(
                    nodes=nodes,
                    requests=requests,
                    seed=effective_seed,
                    sim_time=sim_time,
                    f_req=f_req,
                    p_swap=p_swap,
                    init_fidelity=init_fidelity,
                    verbose_sim=verbose_sim,
                )
            )
    return batch_results


def summarize_fidelity(
    *,
    p_swap: float,
    init_fidelity: float,
    batch: Iterable[RunFidelity],
) -> FidelitySummary:
    samples: List[float] = []
    total_finished = 0
    total_requests = 0
    trial_count = 0

    for run in batch:
        samples.extend(run.fidelities)
        total_finished += run.finished
        total_requests += run.requests
        trial_count += 1

    completion_rate = (
        total_finished / total_requests if total_requests > 0 else 0.0
    )
    avg_fidelity = sum(samples) / len(samples) if samples else None
    min_fidelity = min(samples) if samples else None
    max_fidelity = max(samples) if samples else None

    return FidelitySummary(
        p_swap=p_swap,
        init_fidelity=init_fidelity,
        avg_fidelity=avg_fidelity,
        min_fidelity=min_fidelity,
        max_fidelity=max_fidelity,
        completion_rate=completion_rate,
        total_finished=total_finished,
        trial_count=trial_count,
    )


def sweep_fidelity(
    *,
    p_swap_values: Iterable[float],
    init_fidelities: Iterable[float],
    seeds: Iterable[int],
    runs_per_seed: int,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    verbose_sim: bool,
) -> List[FidelitySummary]:
    summaries: List[FidelitySummary] = []
    for init_fidelity in init_fidelities:
        for p_swap in p_swap_values:
            batch = run_batch(
                seeds=seeds,
                runs_per_seed=runs_per_seed,
                nodes=nodes,
                requests=requests,
                sim_time=sim_time,
                f_req=f_req,
                p_swap=p_swap,
                init_fidelity=init_fidelity,
                verbose_sim=verbose_sim,
            )
            summaries.append(
                summarize_fidelity(
                    p_swap=p_swap, init_fidelity=init_fidelity, batch=batch
                )
            )
    return summaries


def write_csv(path: str, summaries: Iterable[FidelitySummary]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "p_swap,init_fidelity,trial_count,total_finished,completion_rate,"
            "avg_fidelity,min_fidelity,max_fidelity\n"
        )
        for s in summaries:
            avg_f = "" if s.avg_fidelity is None else f"{s.avg_fidelity:.6f}"
            min_f = "" if s.min_fidelity is None else f"{s.min_fidelity:.6f}"
            max_f = "" if s.max_fidelity is None else f"{s.max_fidelity:.6f}"
            f.write(
                f"{s.p_swap:.3f},{s.init_fidelity:.3f},{s.trial_count},"
                f"{s.total_finished},{s.completion_rate:.3f},"
                f"{avg_f},{min_f},{max_f}\n"
            )


def _prepare_grid(
    summaries: Iterable[FidelitySummary],
) -> tuple[List[float], List[float], np.ndarray]:
    p_swaps = sorted({round(s.p_swap, 6) for s in summaries})
    init_fids = sorted({round(s.init_fidelity, 6) for s in summaries})
    grid = np.full((len(init_fids), len(p_swaps)), np.nan, dtype=float)

    index_p = {p: idx for idx, p in enumerate(p_swaps)}
    index_f = {f: idx for idx, f in enumerate(init_fids)}

    for s in summaries:
        p_idx = index_p[round(s.p_swap, 6)]
        f_idx = index_f[round(s.init_fidelity, 6)]
        grid[f_idx, p_idx] = (
            math.nan if s.avg_fidelity is None else s.avg_fidelity
        )
    return p_swaps, init_fids, grid


def generate_heatmap(
    *,
    summaries: Iterable[FidelitySummary],
    output_path: str,
) -> None:
    """p_swap×init_fidelityで平均忠実度のヒートマップを描画する。"""
    p_swaps, init_fids, grid = _prepare_grid(summaries)
    if grid.size == 0:
        raise ValueError("No data to plot")

    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    im = ax.imshow(
        grid,
        origin="lower",
        cmap="viridis",
        aspect="auto",
        interpolation="nearest",
    )

    ax.set_xticks(range(len(p_swaps)), [f"{p:.3f}" for p in p_swaps])
    ax.set_yticks(range(len(init_fids)), [f"{f:.3f}" for f in init_fids])
    ax.set_xlabel("p_swap")
    ax.set_ylabel("init_fidelity")
    ax.set_title("Average final fidelity")

    # 値をセル内に表示（NaNはスキップ）
    for i, fid in enumerate(init_fids):
        for j, p in enumerate(p_swaps):
            val = grid[i, j]
            if not math.isnan(val):
                ax.text(
                    j,
                    i,
                    f"{val:.3f}",
                    ha="center",
                    va="center",
                    color="white" if val < 0.5 else "black",
                    fontsize=8,
                )

    fig.colorbar(im, ax=ax, label="Average fidelity")
    plt.tight_layout()

    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    log.logger.setLevel(getattr(logging, args.log_level.upper()))

    summaries = sweep_fidelity(
        p_swap_values=args.p_swap_values,
        init_fidelities=args.init_fidelities,
        seeds=args.seeds,
        runs_per_seed=args.runs_per_seed,
        nodes=args.nodes,
        requests=args.requests,
        sim_time=args.sim_time,
        f_req=args.f_req,
        verbose_sim=args.verbose_sim,
    )
    write_csv(args.output, summaries)

    if args.plot:
        generate_heatmap(
            summaries=summaries,
            output_path=args.plot_path,
        )

    print("=== 最終もつれ忠実度集計 ===")
    for s in summaries:
        avg_f = "完了なし" if s.avg_fidelity is None else f"{s.avg_fidelity:.4f}"
        print(
            f"p_swap={s.p_swap:.3f} init_fidelity={s.init_fidelity:.3f} "
            f"完了率={s.completion_rate:.3f} 完了数={s.total_finished} "
            f"平均忠実度={avg_f}"
        )
    print(f"\nCSVを書き出しました: {args.output}")
    if args.plot:
        print(f"ヒートマップを書き出しました: {args.plot_path}")


if __name__ == "__main__":
    main()
