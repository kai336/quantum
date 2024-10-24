import logging

from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
from qns.network.topology import LineTopology
import qns.utils.log as log
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp


log.logger.setLevel(logging.INFO)

# constrains
init_fidelity = 1
memory_capacity = 50
send_rate = 10

nodes_number = 5
delay = 0.01

init_fidelities = [1.0, 0.99, 0.98, 0.97, 0.96, 0.95]
#init_fidelities = [0.98]

for init_fidelity in init_fidelities:
    s = Simulator(0, 30, accuracy=10000000)
    log.install(s)
    topo = LineTopology(nodes_number=nodes_number,
                        qchannel_args={"delay": delay},
                        cchannel_args={"delay": delay},
                        memory_args=[{
                            "capacity": memory_capacity,
                            "decoherence_rate": 0.2}],
                        nodes_apps=[EntanglementDistributionApp(init_fidelity=init_fidelity)])

    net = QuantumNetwork(
        topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()

    src = net.get_node("n1")
    dst = net.get_node(f"n{nodes_number}")
    net.add_request(src=src, dest=dst, attr={"send_rate": send_rate})
    net.install(s)
    s.run()
    log.monitor(f"nodes_number: {nodes_number} init_fidelity: {init_fidelity} result_fidelity: {dst.apps[-1].success[0].fidelity}")