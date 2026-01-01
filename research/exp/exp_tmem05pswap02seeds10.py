import argparse
import contextlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
from run_dir import resolve_run_dir, write_config_md

# ------------------------------------------------------------
# バッチ実験用の固定パラメタ（必要に応じてここを書き換え）
# ------------------------------------------------------------
NODES = 50
REQUESTS = 5
SIM_TIME = 1_000_000
F_REQ = 0.8
INIT_FIDELITY = 0.99
SEEDS: List[int] = list(range(10))
RUNS_PER_SEED = 5
VERBOSE_SIM = False
LOG_LEVEL = "INFO"
PSW_THRESHOLD = 0.9
OUTPUT_CSV_NAME = "p_swap_sweep.csv"
REQUIRED_PARAMS = ("t_mem", "p_swap", "psw_threshold", "init_fidelity", "requests", "nodes")


@dataclass
class RunResult:
    seed: int
    finished: int
    throughput: float  # 完了要求 / timeslot（参考情報として保持）
    avg_finish_slot: float | None
    finish_time_sum: float
    fidelity_sum: float


@dataclass
class SweepSummary:
    p_swap: float
    avg_time_per_request: float | None
    total_finished: int
    trial_count: int
    avg_fidelity_per_request: float | None


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
    psw_threshold: Optional[float] = None,
) -> RunResult:
    """単発シミュレーションを実行し、スループットなどを返す。"""
    memory_capacity = 5
    gen_rate = 50
    waxman_size = 100000
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
                psw_threshold=psw_threshold,
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
        # シミュレーション中のprintを無視して出力量を抑える
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            s.run()

    controller_app = controller_node.apps[0]
    finished = len(controller_app.completed_requests)
    sim_span_slot = s.te.time_slot
    throughput = finished / sim_span_slot if sim_span_slot > 0 else 0.0
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
    fidelity_sum = (
        sum(r["fidelity"] for r in controller_app.completed_requests)
        if finished
        else 0.0
    )

    return RunResult(
        seed=seed,
        finished=finished,
        throughput=throughput,
        avg_finish_slot=avg_finish,
        finish_time_sum=finish_time_sum,
        fidelity_sum=fidelity_sum,
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
    psw_threshold: Optional[float] = None,
) -> List[RunResult]:
    """Experiment.py と同じように複数条件でバッチ実行する。"""
    results: List[RunResult] = []
    for base_seed in seeds:
        res = run_single(
            nodes=nodes,
            requests=requests,
            seed=base_seed,
            sim_time=sim_time,
            f_req=f_req,
            p_swap=p_swap,
            init_fidelity=init_fidelity,
            verbose_sim=verbose_sim,
            enable_psw=enable_psw,
            psw_threshold=psw_threshold,
        )
        results.append(res)
    return results


def sweep_p_swap(
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
    psw_threshold: Optional[float] = None,
) -> List[SweepSummary]:
    """p_swapを動かしながらバッチ実験を行い、平均スループットなどを返す。"""
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
            psw_threshold=psw_threshold,
        )
        total_finished = sum(r.finished for r in batch)
        total_finish_time = sum(r.finish_time_sum for r in batch)
        total_fidelity = sum(r.fidelity_sum for r in batch)
        avg_time_per_request = (
            total_finish_time / total_finished if total_finished > 0 else None
        )
        avg_fidelity_per_request = (
            total_fidelity / total_finished if total_finished > 0 else None
        )
        summaries.append(
            SweepSummary(
                p_swap=p_swap,
                avg_time_per_request=avg_time_per_request,
                total_finished=total_finished,
                trial_count=len(batch),
                avg_fidelity_per_request=avg_fidelity_per_request,
            )
        )
    return summaries


def write_csv_stream(output: TextIO, summaries: Iterable[SweepSummary]) -> None:
    """p_swapスイープ結果をCSVとして出力する。"""
    output.write(
        "p_swap,avg_time_per_request_slot,avg_fidelity_per_request,trial_count,total_finished\n"
    )
    for s in summaries:
        avg_time = (
            "" if s.avg_time_per_request is None else f"{s.avg_time_per_request:.2f}"
        )
        avg_fidelity = (
            ""
            if s.avg_fidelity_per_request is None
            else f"{s.avg_fidelity_per_request:.4f}"
        )
        output.write(
            f"{s.p_swap:.1f},{avg_time},{avg_fidelity},{s.trial_count},{s.total_finished}\n"
        )


def main() -> None:
    logging.shutdown
    parser = argparse.ArgumentParser(description="p_swap sweep experiment")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Output directory for this run. Default: data/YYYYMMDD_p_swap_sweep",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=None,
        help="Run date tag (YYYYMMDD). Default: today.",
    )
    args = parser.parse_args()

    run_dir = resolve_run_dir("p_swap_sweep", args.run_dir, args.run_date)
    out_csv = run_dir / OUTPUT_CSV_NAME

    write_config_md(
        run_dir,
        "p_swap_sweep",
        {
            "t_mem": "N/A",
            "p_swap": [round(0.2 + 0.1 * i, 1) for i in range(5)],
            "psw_threshold": PSW_THRESHOLD,
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

    p_swap_values = [round(0.2 + 0.1 * i, 1) for i in range(5)]
    summaries = sweep_p_swap(
        p_swap_values=p_swap_values,
        seeds=SEEDS,
        runs_per_seed=RUNS_PER_SEED,
        nodes=NODES,
        requests=REQUESTS,
        sim_time=SIM_TIME,
        f_req=F_REQ,
        init_fidelity=INIT_FIDELITY,
        verbose_sim=VERBOSE_SIM,
        enable_psw=True,
        psw_threshold=PSW_THRESHOLD,
    )
    with out_csv.open("w", encoding="utf-8") as f:
        write_csv_stream(f, summaries)
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":
    main()
