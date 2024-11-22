import logging

from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
from qns.entity.qchannel import QuantumChannel
from qns.entity.cchannel import ClassicChannel
from qns.network.topology import LineTopology
import qns.utils.log as log
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp

from starttopo import StarTopology

# constrains
init_fidelity = 1
memory_capacity = 50
send_rate = 10

nodes_number = 5
delay = 0.01

length = 100 * 1000 # 単位はm

init_fidelities = [1.0, 0.99, 0.98, 0.97, 0.96, 0.95]

# build star topology
s = Simulator(0, 30, accuracy=10000000)
log.install(s)
topo = StarTopology(nodes_number=nodes_number,
                    qchannel_args={"delay": delay, "length": 100000},
                    cchannel_args={"delay": delay},
                    memory_args=[{
                        "capacity": memory_capacity,
                        "decoherence_rate": 0.2
                    }])
net = QuantumNetwork(
    topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm()
)
net.build_route()

print(net.route.route_table)