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

# 実験パラメータ
NODES = 50
REQUESTS = 5
SIM_TIME = 1_000_000
F_REQ = 0.8
INIT_FIDELITY = 0.99
SEEDS: List[int] = [42, 43, 44]
TOPOLOGY_SEEDS: List[int] = [100, 200, 300, 400, 500]
RUNS_PER_SEED = 2
VERBOSE_SIM = False
LOG_LEVEL = "INFO"
P_SWAP = 0.4
GEN_RATE_VALUES = list(range(10, 55, 5))
OUTPUT_CSV = os.path.join("data", "psw_compare_gen_rate.csv")
OUTPUT_FIG = os.path.join("data", "psw_compare_gen_rate.png")


@dataclass
class RunResult:
    seed: int
    topo_seed: int
    gen_rate: int
    finished: int
    avg_finish_slot: float | None
    finish_time_sum: float


@dataclass
class SweepSummary:
    gen_rate: int
    enable_psw: bool
    avg_time_per_request: float | None
    total_finished: int
    trial_count: int


def run_single(
    *,
    nodes: int,
    requests: int,
    seed: int,
    topo_seed: int,
    sim_time: float,
    f_req: float,
    p_swap: float,
    gen_rate: int,
    init_fidelity: float,
    verbose_sim: bool,
    enable_psw: bool,
) -> RunResult:
    """単発シミュレーションを実行し、リクエスト完了時刻を記録する。"""
    memory_capacity = 5
    waxman_size = 1000
    waxman_alpha = 0.2
    waxman_beta = 0.6

    # トポロジ生成用とシミュレーション用でシードを分ける
    set_seed(topo_seed)

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

    # リクエスト生成などは別のシードで
    set_seed(seed)
    s = Simulator(0, sim_time, SIMULATOR_ACCURACY)

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
        topo_seed=topo_seed,
        gen_rate=gen_rate,
        finished=finished,
        avg_finish_slot=avg_finish,
        finish_time_sum=finish_time_sum,
    )


def run_batch(
    *,
    seeds: Iterable[int],
    topo_seeds: Iterable[int],
    runs_per_seed: int,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    p_swap: float,
    gen_rate: int,
    init_fidelity: float,
    verbose_sim: bool,
    enable_psw: bool,
) -> List[RunResult]:
    """同一条件で複数回実行して統計を取る。"""
    results: List[RunResult] = []
    for topo_seed in topo_seeds:
        for base_seed in seeds:
            for rep in range(runs_per_seed):
                effective_seed = base_seed + rep
                res = run_single(
                    nodes=nodes,
                    requests=requests,
                    seed=effective_seed,
                    topo_seed=topo_seed,
                    sim_time=sim_time,
                    f_req=f_req,
                    p_swap=p_swap,
                    gen_rate=gen_rate,
                    init_fidelity=init_fidelity,
                    verbose_sim=verbose_sim,
                    enable_psw=enable_psw,
                )
                results.append(res)
    return results


def sweep(
    *,
    gen_rate_values: Iterable[int],
    seeds: Iterable[int],
    topo_seeds: Iterable[int],
    runs_per_seed: int,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    p_swap: float,
    init_fidelity: float,
    verbose_sim: bool,
    enable_psw: bool,
) -> List[SweepSummary]:
    """gen_rateを動かしつつポンピング有無ごとの平均完了時間を求める。"""
    summaries: List[SweepSummary] = []
    for gen_rate in gen_rate_values:
        batch = run_batch(
            seeds=seeds,
            topo_seeds=topo_seeds,
            runs_per_seed=runs_per_seed,
            nodes=nodes,
            requests=requests,
            sim_time=sim_time,
            f_req=f_req,
            p_swap=p_swap,
            gen_rate=gen_rate,
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
                gen_rate=gen_rate,
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
        f.write("mode,gen_rate,avg_time_per_request_slot,trial_count,total_finished\n")
        for r in rows:
            avg_time = (
                ""
                if r.avg_time_per_request is None
                else f"{r.avg_time_per_request:.2f}"
            )
            mode = "psw_on" if r.enable_psw else "psw_off"
            f.write(
                f"{mode},{r.gen_rate},{avg_time},{r.trial_count},{r.total_finished}\n"
            )


def plot(
    rows_on: List[SweepSummary],
    rows_off: List[SweepSummary],
    output_path: str,
) -> None:
    """ポンピング有無の平均完了時間を重ね描きする。"""

    def _prepare(rows: List[SweepSummary]) -> Tuple[List[int], List[float]]:
        rows_sorted = sorted(rows, key=lambda x: x.gen_rate)
        xs = [r.gen_rate for r in rows_sorted]
        ys = [
            r.avg_time_per_request
            if r.avg_time_per_request is not None
            else float("nan")
            for r in rows_sorted
        ]
        return xs, ys

    xs_on, ys_on = _prepare(rows_on)
    xs_off, ys_off = _prepare(rows_off)

    plt.figure(figsize=(6.4, 4))
    plt.plot(
        xs_on, ys_on, marker="o", color="#1b73e8", linewidth=2, label="PSWあり"
    )
    plt.plot(
        xs_off, ys_off, marker="s", color="#ef6c00", linewidth=2, label="PSWなし"
    )
    plt.xlabel("gen_rate (1/sec)")
    plt.ylabel("平均リクエスト完了時間 (timeslot)")
    plt.title(f"gen_rateスイープ (p_swap={P_SWAP})")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def main() -> None:
    log.logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
    os.makedirs("data", exist_ok=True)

    print("PSWありのgen_rateスイープを実行します")
    summaries_on = sweep(
        gen_rate_values=GEN_RATE_VALUES,
        seeds=SEEDS,
        topo_seeds=TOPOLOGY_SEEDS,
        runs_per_seed=RUNS_PER_SEED,
        nodes=NODES,
        requests=REQUESTS,
        sim_time=SIM_TIME,
        f_req=F_REQ,
        p_swap=P_SWAP,
        init_fidelity=INIT_FIDELITY,
        verbose_sim=VERBOSE_SIM,
        enable_psw=True,
    )
    print("PSWなしのgen_rateスイープを実行します")
    summaries_off = sweep(
        gen_rate_values=GEN_RATE_VALUES,
        seeds=SEEDS,
        topo_seeds=TOPOLOGY_SEEDS,
        runs_per_seed=RUNS_PER_SEED,
        nodes=NODES,
        requests=REQUESTS,
        sim_time=SIM_TIME,
        f_req=F_REQ,
        p_swap=P_SWAP,
        init_fidelity=INIT_FIDELITY,
        verbose_sim=VERBOSE_SIM,
        enable_psw=False,
    )

    # CSV保存
    all_rows = summaries_on + summaries_off
    write_csv(OUTPUT_CSV, all_rows)
    print(f"CSVを書き出しました: {OUTPUT_CSV}")

    # プロット
    plot(summaries_on, summaries_off, OUTPUT_FIG)
    print(f"グラフを保存しました: {OUTPUT_FIG}")


if __name__ == "__main__":
    main()
