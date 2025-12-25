import argparse
import contextlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
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
OUTPUT_CSV_NAME = "swap_waiting.csv"
REQUIRED_PARAMS = ("t_mem", "p_swap", "psw_threshold", "init_fidelity", "requests", "nodes")


@dataclass
class RunResult:
    seed: int
    finished: int
    avg_finish_slot: float | None
    avg_wait_per_swap: float | None
    avg_wait_per_request: float | None
    swap_wait_times: List[int]


@dataclass
class SweepSummary:
    p_swap: float
    avg_wait_per_swap: float | None
    avg_wait_per_request: float | None
    total_swap_waits: int
    trial_count: int


def _average_wait_per_request(wait_times_by_req: dict[str, List[int]]) -> float | None:
    per_req_avgs: List[float] = []
    for waits in wait_times_by_req.values():
        if waits:
            per_req_avgs.append(mean(waits))
    if not per_req_avgs:
        return None
    return mean(per_req_avgs)


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
    """単発シミュレーションを実行し、swap待機時間を計測する。"""
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
    avg_finish = (
        sum(r["finish_time"] for r in controller_app.completed_requests) / finished
        if finished
        else None
    )

    waits = controller_app.swap_wait_times
    avg_wait_per_swap = mean(waits) if waits else None
    avg_wait_per_request = _average_wait_per_request(
        controller_app.swap_wait_times_by_req
    )

    return RunResult(
        seed=seed,
        finished=finished,
        avg_finish_slot=avg_finish,
        avg_wait_per_swap=avg_wait_per_swap,
        avg_wait_per_request=avg_wait_per_request,
        swap_wait_times=waits,
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
    """複数条件でバッチ実行する。"""
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
    """p_swapを動かしながらバッチ実験を行い、swap待機時間を返す。"""
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
        swap_wait_count = sum(len(r.swap_wait_times) for r in batch)
        total_wait_time = sum(sum(r.swap_wait_times) for r in batch)
        avg_wait_per_swap = (
            total_wait_time / swap_wait_count if swap_wait_count > 0 else None
        )

        per_req_avgs: List[float] = []
        for res in batch:
            req_avg = res.avg_wait_per_request
            if req_avg is not None:
                per_req_avgs.append(req_avg)
        avg_wait_per_request = mean(per_req_avgs) if per_req_avgs else None

        summaries.append(
            SweepSummary(
                p_swap=p_swap,
                avg_wait_per_swap=avg_wait_per_swap,
                avg_wait_per_request=avg_wait_per_request,
                total_swap_waits=swap_wait_count,
                trial_count=len(batch),
            )
        )
    return summaries


def write_csv_stream(output: TextIO, summaries: Iterable[SweepSummary]) -> None:
    """p_swapスイープ結果をCSVとして出力する。"""
    output.write(
        "p_swap,avg_wait_per_swap_slot,avg_wait_per_request_slot,trial_count,total_swap_waits\n"
    )
    for s in summaries:
        avg_wait_swap = (
            "" if s.avg_wait_per_swap is None else f"{s.avg_wait_per_swap:.2f}"
        )
        avg_wait_req = (
            "" if s.avg_wait_per_request is None else f"{s.avg_wait_per_request:.2f}"
        )
        output.write(
            f"{s.p_swap:.1f},{avg_wait_swap},{avg_wait_req},{s.trial_count},{s.total_swap_waits}\n"
        )


def main() -> None:
    logging.shutdown
    parser = argparse.ArgumentParser(description="Swap waiting time sweep experiment")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Output directory for this run. Default: data/YYYYMMDD_swap_waiting",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=None,
        help="Run date tag (YYYYMMDD). Default: today.",
    )
    args = parser.parse_args()

    run_dir = resolve_run_dir("swap_waiting", args.run_dir, args.run_date)
    out_csv = run_dir / OUTPUT_CSV_NAME

    write_config_md(
        run_dir,
        "swap_waiting",
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
