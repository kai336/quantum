from qns.simulator.simulator import Simulator
from qns.network.topology import LineTopology
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology
import qns.utils.log as log

import logging

init_fidelity = 0.99 # the initial entanglement's fidelity
nodes_number = 10 # the number of nodes
qchannel_delay = 0.05 # the delay of quantum channels
cchannel_delay = 0.05 # the delay of classic channels
memory_capacity = 50 # the size of quantum memories
send_rate = 1 # the send rate
requests_number = 2 # the number of sessions (SD-pairs)

#generate the simulator
s = Simulator(0, 1, accuracy=1000000)

#set the log's level
log.logger.setLevel(logging.DEBUG)
log.install(s)

# generate a random topology using the parameters above
# each node will install EntanglementDistributionApp for hop-by-hop entanglement distribution
topo = LineTopology(nodes_number=nodes_number,
    qchannel_args={"delay": qchannel_delay},
    cchannel_args={"delay": cchannel_delay},
    memory_args=[{"capacity": memory_capacity}],
    nodes_apps=[EntanglementDistributionApp(init_fidelity=init_fidelity)])

# build the network, with Dijkstra's routing algorithm
net = QuantumNetwork( topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())



net.build_route()

net.random_requests(requests_number, attr={"send_rate": send_rate})

net.install(s)

s.run()