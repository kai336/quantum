from qns.simulator.simulator import Simulator
from qns.network.topology import RandomTopology
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology
import qns.utils.log as log

import logging

init_fidelity = 0.99 # the initial entanglement's fidelity
nodes_number = 15 # the number of nodes
lines_number = 45 # the number of quantum channels
qchannel_delay = 0.05 # the delay of quantum channels
cchannel_delay = 0.05 # the delay of classic channels
memory_capacity = 50 # the size of quantum memories
send_rate = 10 # the send rate
requests_number = 5 # the number of sessions (SD-pairs)

#generate the simulator
s = Simulator(0, 10, accuracy=1000000)

#set the log's level
log.logger.setLevel(logging.DEBUG)
log.install(s)

# generate a random topology using the parameters above
# each node will install EntanglementDistributionApp for hop-by-hop entanglement distribution
topo = RandomTopology(nodes_number=nodes_number,
    lines_number=lines_number,
    qchannel_args={"delay": qchannel_delay},
    cchannel_args={"delay": cchannel_delay},
    memory_args=[{"capacity": memory_capacity}],
    nodes_apps=[EntanglementDistributionApp(init_fidelity=init_fidelity)])

# build the network, with Dijkstra's routing algorithm
net = QuantumNetwork( topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())


n1 = net.get_node('n1')
n2 = net.get_node('n2')
# build the routing table
net.build_route()

# show requests
net.random_requests(requests_number, attr={"send_rate": send_rate})
print('requests: ', net.requests)
print('n1 requests: ', n1.requests)


# show nodes
nodes = net.nodes
print('nodes:', nodes, sep=' ')

# query test

res = net.query_route(n1, n2)
print('query result: ', res)
next_hop = res[0][1]
print('next hop: ', next_hop)