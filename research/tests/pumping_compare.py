import argparse
import contextlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import matplotlib.pyplot as plt

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
from exp.run_dir import resolve_run_dir, write_config_md

# 実験パラメータ（適宜変更可）
NODES = 50
REQUESTS = 5
SIM_TIME = 1_000_000
F_REQ = 0.8
INIT_FIDELITY = 0.99
SEEDS: List[int] = [42, 43, 44]
RUNS_PER_SEED = 2
VERBOSE_SIM = False
LOG_LEVEL = "INFO"
P_SWAP_VALUES = [0.2, 0.3, 0.4, 0.5, 0.6]
OUTPUT_CSV_NAME = "psw_compare.csv"
OUTPUT_FIG_NAME = "psw_compare.png"
REQUIRED_PARAMS = ("t_mem", "p_swap", "psw_threshold", "init_fidelity", "requests", "nodes")


@dataclass
class RunResult:
    seed: int
    finished: int
    avg_finish_slot: float | None
    finish_time_sum: float


@dataclass
class SweepSummary:
    p_swap: float
    enable_psw: bool
    avg_time_per_request: float | None
    total_finished: int
    trial_count: int


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
    enable_psw: bool,
) -> RunResult:
    """単発シミュレーションを実行し、リクエスト完了時刻を記録する。"""
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
                enable_psw=enable_psw,
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
    finished = len(controller_app.completed_requests)
    avg_finish = (
        sum(r["finish_time"] for r in controller_app.completed_requests) / finished
        if finished
        else None
    )
    finish_time_sum = (
        sum(r["finish_time"] for r in controller_app.completed_requests)
        if finished
        else 0.0
    )

    return RunResult(
        seed=seed,
        finished=finished,
        avg_finish_slot=avg_finish,
        finish_time_sum=finish_time_sum,
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
    enable_psw: bool,
) -> List[RunResult]:
    """同一条件で複数回実行して統計を取る。"""
    results: List[RunResult] = []
    for base_seed in seeds:
        for rep in range(runs_per_seed):
            effective_seed = base_seed + rep
            res = run_single(
                nodes=nodes,
                requests=requests,
                seed=effective_seed,
                sim_time=sim_time,
                f_req=f_req,
                p_swap=p_swap,
                init_fidelity=init_fidelity,
                verbose_sim=verbose_sim,
                enable_psw=enable_psw,
            )
            results.append(res)
    return results


def sweep(
    *,
    p_swap_values: Iterable[float],
    seeds: Iterable[int],
    runs_per_seed: int,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    init_fidelity: float,
    verbose_sim: bool,
    enable_psw: bool,
) -> List[SweepSummary]:
    """p_swapを動かしつつポンピング有無ごとの平均完了時間を求める。"""
    summaries: List[SweepSummary] = []
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
            enable_psw=enable_psw,
        )
        total_finished = sum(r.finished for r in batch)
        total_finish_time = sum(r.finish_time_sum for r in batch)
        avg_time_per_request = (
            total_finish_time / total_finished if total_finished > 0 else None
        )
        summaries.append(
            SweepSummary(
                p_swap=p_swap,
                enable_psw=enable_psw,
                avg_time_per_request=avg_time_per_request,
                total_finished=total_finished,
                trial_count=len(batch),
            )
        )
    return summaries


def write_csv(path: str, rows: Iterable[SweepSummary]) -> None:
    """結果をCSVに保存する。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("mode,p_swap,avg_time_per_request_slot,trial_count,total_finished\n")
        for r in rows:
            avg_time = "" if r.avg_time_per_request is None else f"{r.avg_time_per_request:.2f}"
            mode = "psw_on" if r.enable_psw else "psw_off"
            f.write(
                f"{mode},{r.p_swap:.1f},{avg_time},{r.trial_count},{r.total_finished}\n"
            )


def plot(
    rows_on: List[SweepSummary],
    rows_off: List[SweepSummary],
    output_path: str,
) -> None:
    """ポンピング有無の平均完了時間を重ね描きする。"""
    def _prepare(rows: List[SweepSummary]) -> Tuple[List[float], List[float]]:
        rows_sorted = sorted(rows, key=lambda x: x.p_swap)
        xs = [r.p_swap for r in rows_sorted]
        ys = [
            r.avg_time_per_request if r.avg_time_per_request is not None else float("nan")
            for r in rows_sorted
        ]
        return xs, ys

    xs_on, ys_on = _prepare(rows_on)
    xs_off, ys_off = _prepare(rows_off)

    plt.figure(figsize=(6.4, 4))
    plt.plot(xs_on, ys_on, marker="o", color="#1b73e8", linewidth=2, label="Pumping on")
    plt.plot(xs_off, ys_off, marker="s", color="#ef6c00", linewidth=2, label="Pumping off")
    plt.xlabel("p_swap")
    plt.ylabel("Average request completion time (timeslot)")
    plt.title("Average completion time vs p_swap (PSW on/off)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def main() -> None:
    log.logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
    parser = argparse.ArgumentParser(description="PSW on/off compare sweep")
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Output directory for this run. Default: data/YYYYMMDD_psw_compare",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=None,
        help="Run date tag (YYYYMMDD). Default: today.",
    )
    args = parser.parse_args()

    run_dir = resolve_run_dir("psw_compare", args.run_dir, args.run_date)
    output_csv = os.path.join(run_dir, OUTPUT_CSV_NAME)
    output_fig = os.path.join(run_dir, OUTPUT_FIG_NAME)
    write_config_md(
        Path(run_dir),
        "psw_compare",
        {
            "t_mem": "N/A",
            "p_swap": P_SWAP_VALUES,
            "psw_threshold": "N/A",
            "init_fidelity": INIT_FIDELITY,
            "requests": REQUESTS,
            "nodes": NODES,
            "seeds": SEEDS,
            "runs_per_seed": RUNS_PER_SEED,
            "sim_time": SIM_TIME,
            "f_req": F_REQ,
        },
        REQUIRED_PARAMS,
    )

    print("Running sweep with PSW enabled")
    summaries_on = sweep(
        p_swap_values=P_SWAP_VALUES,
        seeds=SEEDS,
        runs_per_seed=RUNS_PER_SEED,
        nodes=NODES,
        requests=REQUESTS,
        sim_time=SIM_TIME,
        f_req=F_REQ,
        init_fidelity=INIT_FIDELITY,
        verbose_sim=VERBOSE_SIM,
        enable_psw=True,
    )
    print("Running sweep with PSW disabled")
    summaries_off = sweep(
        p_swap_values=P_SWAP_VALUES,
        seeds=SEEDS,
        runs_per_seed=RUNS_PER_SEED,
        nodes=NODES,
        requests=REQUESTS,
        sim_time=SIM_TIME,
        f_req=F_REQ,
        init_fidelity=INIT_FIDELITY,
        verbose_sim=VERBOSE_SIM,
        enable_psw=False,
    )

    # CSV保存
    all_rows = summaries_on + summaries_off
    write_csv(output_csv, all_rows)
    print(f"CSVを書き出しました: {output_csv}")

    # プロット
    plot(summaries_on, summaries_off, output_fig)
    print(f"グラフを保存しました: {output_fig}")


if __name__ == "__main__":
    main()
