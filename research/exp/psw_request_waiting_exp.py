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
P_SWAP = 0.4
SEEDS: List[int] = list(range(10))
RUNS_PER_SEED = 5
VERBOSE_SIM = False
LOG_LEVEL = "INFO"
PSW_THRESHOLD = 0.9
OUTPUT_CSV_NAME = "psw_request_waiting.csv"
REQUIRED_PARAMS = ("t_mem", "p_swap", "psw_threshold", "init_fidelity", "requests", "nodes")


@dataclass
class RunResult:
    enable_psw: bool
    seed: int
    finished: int
    avg_wait_per_request: float | None
    wait_times: List[int]
    psw_purify_attempts: int
    psw_purify_successes: int
    psw_purify_fails: int
    psw_cancelled: int


@dataclass
class PSWSummary:
    enable_psw: bool
    avg_wait_per_request: float | None
    total_finished: int
    trial_count: int


@dataclass
class PSWStatsSummary:
    enable_psw: bool
    avg_wait_per_request: float | None
    total_finished: int
    trial_count: int
    psw_purify_attempts: int
    psw_purify_successes: int
    psw_purify_fails: int
    psw_cancelled: int

    @property
    def psw_purify_attempts_per_finished(self) -> float | None:
        if self.total_finished <= 0:
            return None
        return self.psw_purify_attempts / self.total_finished


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
    """単発シミュレーションを実行し、リクエスト完了までの待ち時間を記録する。"""
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
    waits = [r["finish_time"] for r in controller_app.completed_requests]
    avg_wait = mean(waits) if waits else None
    psw_attempts = getattr(controller_app, "psw_purify_scheduled", 0) if enable_psw else 0
    psw_successes = getattr(controller_app, "psw_purify_success", 0) if enable_psw else 0
    psw_fails = getattr(controller_app, "psw_purify_fail", 0) if enable_psw else 0
    psw_cancelled = getattr(controller_app, "psw_cancelled", 0) if enable_psw else 0

    return RunResult(
        enable_psw=enable_psw,
        seed=seed,
        finished=finished,
        avg_wait_per_request=avg_wait,
        wait_times=waits,
        psw_purify_attempts=psw_attempts,
        psw_purify_successes=psw_successes,
        psw_purify_fails=psw_fails,
        psw_cancelled=psw_cancelled,
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


def compare_psw_on_off(
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
    psw_threshold: Optional[float] = None,
) -> List[PSWSummary]:
    """PSWのON/OFFでリクエスト待ち時間を比較する。"""
    summaries: List[PSWSummary] = []
    for enable_psw in (False, True):
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
        total_wait = sum(sum(r.wait_times) for r in batch)
        avg_wait_per_request = (
            total_wait / total_finished if total_finished > 0 else None
        )
        summaries.append(
            PSWSummary(
                enable_psw=enable_psw,
                avg_wait_per_request=avg_wait_per_request,
                total_finished=total_finished,
                trial_count=len(batch),
            )
        )
    return summaries


def compare_psw_on_off_stats(
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
    psw_threshold: Optional[float] = None,
) -> List[PSWStatsSummary]:
    """PSWのON/OFFで待ち時間とPSW発火回数なども含めて比較する。"""
    summaries: List[PSWStatsSummary] = []
    for enable_psw in (False, True):
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
        total_wait = sum(sum(r.wait_times) for r in batch)
        avg_wait_per_request = (
            total_wait / total_finished if total_finished > 0 else None
        )
        psw_attempts = sum(r.psw_purify_attempts for r in batch)
        psw_successes = sum(r.psw_purify_successes for r in batch)
        psw_fails = sum(r.psw_purify_fails for r in batch)
        psw_cancelled = sum(r.psw_cancelled for r in batch)
        summaries.append(
            PSWStatsSummary(
                enable_psw=enable_psw,
                avg_wait_per_request=avg_wait_per_request,
                total_finished=total_finished,
                trial_count=len(batch),
                psw_purify_attempts=psw_attempts,
                psw_purify_successes=psw_successes,
                psw_purify_fails=psw_fails,
                psw_cancelled=psw_cancelled,
            )
        )
    return summaries


def write_csv_stream(output: TextIO, summaries: Iterable[PSWSummary]) -> None:
    """比較結果をCSVとして出力する。"""
    output.write(
        "enable_psw,avg_wait_per_request_slot,trial_count,total_finished\n"
    )
    for s in summaries:
        avg_wait = (
            "" if s.avg_wait_per_request is None else f"{s.avg_wait_per_request:.2f}"
        )
        flag = "on" if s.enable_psw else "off"
        output.write(f"{flag},{avg_wait},{s.trial_count},{s.total_finished}\n")


def main() -> None:
    logging.shutdown
    parser = argparse.ArgumentParser(description="PSW request waiting experiment")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Output directory for this run. Default: data/YYYYMMDD_psw_request_waiting",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=None,
        help="Run date tag (YYYYMMDD). Default: today.",
    )
    args = parser.parse_args()

    run_dir = resolve_run_dir("psw_request_waiting", args.run_dir, args.run_date)
    out_csv = run_dir / OUTPUT_CSV_NAME
    write_config_md(
        run_dir,
        "psw_request_waiting",
        {
            "t_mem": "N/A",
            "p_swap": P_SWAP,
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

    summaries = compare_psw_on_off(
        seeds=SEEDS,
        runs_per_seed=RUNS_PER_SEED,
        nodes=NODES,
        requests=REQUESTS,
        sim_time=SIM_TIME,
        f_req=F_REQ,
        p_swap=P_SWAP,
        init_fidelity=INIT_FIDELITY,
        verbose_sim=VERBOSE_SIM,
        psw_threshold=PSW_THRESHOLD,
    )
    with out_csv.open("w", encoding="utf-8") as f:
        write_csv_stream(f, summaries)
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":
    main()
