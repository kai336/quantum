from qns.network.topology import RandomTopology
from qns.network.network import QuantumNetwork
from qns.network.route import DijkstraRouteAlgorithm
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp

memory_capacity = 1
init_fidelity = 0.8

topo = RandomTopology(
    nodes_number=5,
    lines_number=10,
    qchannel_args={"delay": 0.05, "bandwidth": 10},
    cchannel_args={"delay": 0.05},
    memory_args=[{"capacity": memory_capacity}],
    nodes_apps=[EntanglementDistributionApp(init_fidelity=init_fidelity)])

# use the ``DijkstraRouteAlgorithm``, using the bandwidth as the ``metric_func``
route = DijkstraRouteAlgorithm(metric_func=lambda qchannel: qchannel.bandwidth)

# build the network, classic topology follows the quantum topology
net = QuantumNetwork(topo=topo, route = route)

net.build_route()

print(net.route.route_table)