from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
import qns.utils.log as log
from qns.network.topology import GridTopology
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology

import logging
import numpy as np
import random

from OpportunisticApp2 import OpportunistcApp2

fidelity = 0.8
memory_capacity = 5
memory_time = 0.1

drop_rate = 0.0  # p_genでもつれ生成の確率を管理しているので０でおｋ

lifetime = 30
decoherence_rate = 1 / lifetime

gen_rate = 1  # １秒あたりのもつれ生成チャレンジ回数

p_gen = 0.1  # もつれ生成成功確率
p_swap = 0.8  # swapping成功確率

nodes_number = 7
qchannel_delay = 0.0
cchannel_delay = 0.0

request_number = 5

M = 5
N = 20
L = 6
p_swap = 0.8


def set_seed(seed: int = None):
    random.seed(seed)
    np.random.seed(seed=seed)


size_of_grid = 5


# a single simulation
def exp3(
    islog: bool = False,
    isopp: bool = False,
    p_gen: float = p_gen,
    p_swap: float = p_swap,
    L: float = lifetime,
    N: int = request_number,
    M: int = size_of_grid,
    seed: int = None,
    alpha: float = 0,
):
    s = Simulator(0, 1000000, accuracy=1)
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)
    drop_rate = 0.0
    topo2 = GridTopology(
        nodes_number=M**2,
        nodes_apps=[
            OpportunistcApp2(
                p_gen=p_gen, p_swap=p_swap, lifetime=L, isopp=isopp, alpha=alpha
            )
        ],
        qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
        cchannel_args={"delay": cchannel_delay},
        memory_args=[{"capacity": memory_capacity}],
    )

    net = QuantumNetwork(
        topo=topo2, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm()
    )
    net.build_route()

    set_seed(seed)
    net.random_requests(number=N, allow_overlay=True)
    set_seed(None)

    log.debug(f"{net.requests}")

    net.install(s)
    s.run()
    totalwaitingtime = net.runtime
    # print(p_gen, waitingtime)
    return totalwaitingtime


# main experiment
def exp4():
    import time

    start = time.time()
    M = 5
    N = 20
    L = 6
    p_swap = 1.0

    p_gens = np.linspace(0.1, 1.0, 10)
    avarage_nopp = []
    avarage_opp = []
    for p in p_gens:
        totalwaitings_nopp = []
        totalwaitings_opp = []
        for seed in range(5):
            for i in range(10):
                waitingtime_nopp = exp3(
                    isopp=False, p_gen=p, p_swap=p_swap, L=L, N=N, M=M, seed=seed
                )
                totalwaitings_nopp.append(waitingtime_nopp)
                waitingtime_opp = exp3(
                    isopp=True, p_gen=p, p_swap=p_swap, L=L, N=N, M=M, seed=seed
                )
                totalwaitings_opp.append(waitingtime_opp)
                print(seed, p, i, "res", waitingtime_nopp, waitingtime_opp)
        avarage_waitingtime_nopp = sum(totalwaitings_nopp) / len(totalwaitings_nopp)
        avarage_waitingtime_opp = sum(totalwaitings_opp) / len(totalwaitings_opp)
        avarage_nopp.append(avarage_waitingtime_nopp)
        avarage_opp.append(avarage_waitingtime_opp)

    end = time.time()
    time_diff = end - start

    print(avarage_nopp)
    print(avarage_opp)
    print(time_diff)


exp4()
