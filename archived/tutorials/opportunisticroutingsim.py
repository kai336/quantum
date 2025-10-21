from qns.network.topology import GridTopology
from qns.network.topology.topo import ClassicTopology
from qns.network.network import QuantumNetwork
import math
from typing import Callable, Dict, List, Tuple, Union
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.entity.cchannel.cchannel import ClassicChannel
from qns.network.route.route import RouteImpl, NetworkRouteError

class D_NOPP():
    INF = math.inf

    def __init__(self):
        self.name = 'D_NOPP'
        self.route_table = {}
        
    def build(self, nodes: List[QNode], channels: List[Union[QuantumChannel, ClassicChannel]]):
        for n in nodes:
            pass

    pass
            

class D_OPP():
    INF = math.inf

    def __init__(self):
        self.name = 'D_OPP'
        self.route_table = {}

    def build(self, nodes: List[QNode], channels: List[Union[QuantumChannel, ClassicChannel]]):
        for n in nodes:
            pass
    
    pass



#setting variables

p_gen = 0.5     # the success rate of entanglement generation betweene two adjacent nodes
p_swap = 0.5    # the success rete of every swapping
L = 30          # the lifetime of an entangled pair
N = 10          # the number of requests
M = 5           # the scale of grid topology (M*M)
k = 1           # the opportunism degree

nodes_number = M * M

#generate topology & network

topo = GridTopology(nodes_number=nodes_number)
net = QuantumNetwork(topo=topo, classic_topo=ClassicTopology.Follow)
node_list = net.nodes
qchannel_list = net.qchannels
# print(node_list)
# print(qchannel_list)
net.random_requests(number=N)
print(net.requests)