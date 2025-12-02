import contextlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

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

# ------------------------------------------------------------
# バッチ実験用の固定パラメタ（必要に応じてここを書き換え）
# ------------------------------------------------------------
NODES = 50
REQUESTS = 5
SIM_TIME = 1_000_000
F_REQ = 0.8
INIT_FIDELITY = 0.99
SEEDS: List[int] = [42, 43, 44]
RUNS_PER_SEED = 2
VERBOSE_SIM = False
LOG_LEVEL = "INFO"


@dataclass
class RunResult:
    seed: int
    finished: int
    throughput: float  # 完了要求 / timeslot（参考情報として保持）
    avg_finish_slot: float | None
    finish_time_sum: float


@dataclass
class SweepSummary:
    p_swap: float
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
) -> RunResult:
    """単発シミュレーションを実行し、スループットなどを返す。"""
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

    return RunResult(
        seed=seed,
        finished=finished,
        throughput=throughput,
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
) -> List[RunResult]:
    """Experiment.py と同じように複数条件でバッチ実行する。"""
    results: List[RunResult] = []
    for base_seed in seeds:
        for rep in range(runs_per_seed):
            # 同一シードで繰り返す場合でも乱数をずらす
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
        )
        total_finished = sum(r.finished for r in batch)
        total_finish_time = sum(r.finish_time_sum for r in batch)
        avg_time_per_request = (
            total_finish_time / total_finished if total_finished > 0 else None
        )
        summaries.append(
            SweepSummary(
                p_swap=p_swap,
                avg_time_per_request=avg_time_per_request,
                total_finished=total_finished,
                trial_count=len(batch),
            )
        )
    return summaries


def write_csv(path: str, summaries: Iterable[SweepSummary]) -> None:
    """p_swapスイープ結果をCSVに出力する。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("p_swap,avg_time_per_request_slot,trial_count,total_finished\n")
        for s in summaries:
            avg_time = "" if s.avg_time_per_request is None else f"{s.avg_time_per_request:.2f}"
            f.write(f"{s.p_swap:.1f},{avg_time},{s.trial_count},{s.total_finished}\n")


def main() -> None:
    log.logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

    p_swap_values = [round(0.2 + 0.1 * i, 1) for i in range(5)]
    os.makedirs("data", exist_ok=True)
    output_csv = os.path.join("data", "p_swap_throughput_sweep.csv")

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
    )
    write_csv(output_csv, summaries)

    print("p_swapごとの平均リクエスト実行時間(timeslot)")
    for s in summaries:
        avg_time = (
            "完了なし" if s.avg_time_per_request is None else f"{s.avg_time_per_request:.2f}"
        )
        print(
            f"p_swap={s.p_swap:.1f} 平均実行時間(timeslot)={avg_time} "
            f"試行数={s.trial_count} 完了要求数={s.total_finished}"
        )
    print(f"\nCSVを書き出しました: {output_csv}")


if __name__ == "__main__":
    main()
