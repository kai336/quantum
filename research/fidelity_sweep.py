import argparse
import contextlib
import logging
import os
from dataclasses import dataclass
from typing import Iterable, List

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
class FidelityResult:
    p_swap: float
    init_fidelity: float
    finished: int
    completion_rate: float
    avg_fidelity: float | None
    min_fidelity: float | None
    max_fidelity: float | None
    avg_finish_slot: float | None
    throughput: float


def parse_float_list(values: str) -> List[float]:
    return [float(v.strip()) for v in values.split(",") if v.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="フィデリティを主指標にした init_fidelity × p_swap スイープ"
    )
    parser.add_argument(
        "--init-fidelities",
        type=parse_float_list,
        default=[0.9, 0.925, 0.95],
        help="init_fidelity の候補 (カンマ区切り)",
    )
    parser.add_argument(
        "--p-swap-values",
        type=parse_float_list,
        default=[0.2, 0.4, 0.6],
        help="p_swap の候補 (カンマ区切り)",
    )
    parser.add_argument("--nodes", type=int, default=50, help="Waxman のノード数")
    parser.add_argument("--requests", type=int, default=5, help="要求数")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード")
    parser.add_argument(
        "--sim-time",
        type=float,
        default=100_000,
        help="シミュレーション終了時刻（timeslot単位）",
    )
    parser.add_argument(
        "--f-req", type=float, default=0.8, help="最小要求忠実度(f_req)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="ログレベル (DEBUG/INFO/WARNING/ERROR)",
    )
    parser.add_argument(
        "--verbose-sim",
        action="store_true",
        help="シミュレーション中の標準出力を抑制しない",
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
) -> FidelityResult:
    target_fidelity = 0.8
    memory_capacity = 5
    memory_time = 0.1
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
    finished = len(controller_app.completed_requests)
    sim_span_slot = s.te.time_slot
    throughput = finished / sim_span_slot if sim_span_slot > 0 else 0.0
    fidelities = [r["fidelity"] for r in controller_app.completed_requests]
    avg_finish = (
        sum(r["finish_time"] for r in controller_app.completed_requests) / finished
        if finished
        else None
    )

    return FidelityResult(
        p_swap=p_swap,
        init_fidelity=init_fidelity,
        finished=finished,
        completion_rate=finished / requests if requests > 0 else 0.0,
        avg_fidelity=sum(fidelities) / len(fidelities) if fidelities else None,
        min_fidelity=min(fidelities) if fidelities else None,
        max_fidelity=max(fidelities) if fidelities else None,
        avg_finish_slot=avg_finish,
        throughput=throughput,
    )


def sweep(
    *,
    init_fidelities: Iterable[float],
    p_swap_values: Iterable[float],
    nodes: int,
    requests: int,
    seed: int,
    sim_time: float,
    f_req: float,
    verbose_sim: bool,
) -> List[FidelityResult]:
    results: List[FidelityResult] = []
    for init_fidelity in init_fidelities:
        for p_swap in p_swap_values:
            res = run_single(
                nodes=nodes,
                requests=requests,
                seed=seed,
                sim_time=sim_time,
                f_req=f_req,
                p_swap=p_swap,
                init_fidelity=init_fidelity,
                verbose_sim=verbose_sim,
            )
            results.append(res)
    return results


def main() -> None:
    args = parse_args()
    log.logger.setLevel(getattr(logging, args.log_level.upper()))

    results = sweep(
        init_fidelities=args.init_fidelities,
        p_swap_values=args.p_swap_values,
        nodes=args.nodes,
        requests=args.requests,
        seed=args.seed,
        sim_time=args.sim_time,
        f_req=args.f_req,
        verbose_sim=args.verbose_sim,
    )

    print(
        "p_swap,init_fidelity,finished,completion_rate,"
        "avg_fidelity,min_fidelity,max_fidelity,"
        "avg_finish_slot,throughput(/timeslot)"
    )
    for r in results:
        avg_finish_slot = (
            "" if r.avg_finish_slot is None else f"{r.avg_finish_slot:.2f}"
        )
        avg_fid = "" if r.avg_fidelity is None else f"{r.avg_fidelity:.6f}"
        min_fid = "" if r.min_fidelity is None else f"{r.min_fidelity:.6f}"
        max_fid = "" if r.max_fidelity is None else f"{r.max_fidelity:.6f}"
        print(
            f"{r.p_swap:.3f},{r.init_fidelity:.3f},{r.finished},"
            f"{r.completion_rate:.3f},{avg_fid},{min_fid},{max_fid},"
            f"{avg_finish_slot},{r.throughput:.6f}"
        )


if __name__ == "__main__":
    main()
