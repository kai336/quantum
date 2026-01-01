import argparse
import logging
import sys
from pathlib import Path

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=50, help="Waxmanのノード数")
    parser.add_argument("--requests", type=int, default=5, help="要求数")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード")
    parser.add_argument(
        "--sim-time", type=float, default=1_000_000, help="シミュレーション終了時刻"
    )
    parser.add_argument(
        "--f-req", type=float, default=0.8, help="最小要求忠実度(f_req)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 初期値
    p_swap = 0.4
    target_fidelity = 0.8
    memory_capacity = 5
    memory_time = 0.1
    gen_rate = 50  # １秒あたりのもつれ生成回数
    f_req = args.f_req  # 最小要求忠実度
    init_fidelity = 0.99
    l0_link_max = 5  # リンクレベルEPのバッファ数 メモリ管理に使う
    # Waxman topoのパラメタ
    waxman_size = 1000
    waxman_alpha = 0.2
    waxman_beta = 0.6

    s = Simulator(0, args.sim_time, SIMULATOR_ACCURACY)
    log.logger.setLevel(logging.DEBUG)
    set_seed(args.seed)

    topo = WaxmanTopology(
        nodes_number=args.nodes,
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
    net.random_requests(number=args.requests)

    controller_node = QNode(
        name="controller",
        apps=[ControllerApp(p_swap=p_swap, f_req=f_req, gen_rate=gen_rate)],
    )
    net.add_node(controller_node)

    net.install(s)
    net.build_route()
    if net.requests:
        net.query_route(net.requests[0].src, net.requests[0].dest)

    s.run()


if __name__ == "__main__":
    main()
