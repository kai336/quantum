from qns.simulator.simulator import Simulator
from qns.network.topology import GridTopology
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology
import qns.utils.log as log
from qns.utils.rnd import set_seed

import logging
import numpy as np


init_fidelity = 0.99 # the initial entanglement's fidelity
nodes_number = 16 # the number of nodes
qchannel_delay = 0.05 # the delay of quantum channels
cchannel_delay = 0.05 # the delay of classic channels
memory_capacity = 50 # the size of quantum memories
send_rate = 1 # the send rate
requests_number = 5 # the number of sessions (SD-pairs)
drop_rate = 0.1


def sim(drop_rate=0.1, memory_capacity=50):
    #generate the simulator
    s = Simulator(0, 2, accuracy=1000000)

    #set the log's level
    log.logger.setLevel(logging.INFO)
    log.install(s)

    # generate a random topology using the parameters above
    # each node will install EntanglementDistributionApp for hop-by-hop entanglement distribution
    topo = GridTopology(nodes_number=nodes_number,
        qchannel_args={"delay": qchannel_delay, "drop_rate": drop_rate},
        cchannel_args={"delay": cchannel_delay},
        memory_args=[{"capacity": memory_capacity}],
        nodes_apps=[EntanglementDistributionApp(init_fidelity=init_fidelity)])

    # build the network, with Dijkstra's routing algorithm
    net = QuantumNetwork(topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())

    set_seed(1)

    net.random_requests(number=requests_number, attr={"send_rate": send_rate})


    #net.random_requests(requests_number, attr={"send_rate": send_rate})
    net.build_route()

    net.install(s)

    s.run()

    # count the number of successful entanglement distribution for each session
    results = [req.src.apps[0].success_count for req in net.requests]

    # log the results
    log.monitor(requests_number, nodes_number, results, s.time_spend, sep=" ")

#for drop_rate in np.linspace(0.1, 0.5, 5):
    #sim(drop_rate=drop_rate)

for cap in range(1, 5):
    sim(memory_capacity=cap)


