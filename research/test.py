from edp.alg.edp import qnet2DictConverter
from edp.app.controller_app import ControllerApp
from edp.app.node_app import NodeApp
from edp.sim.op import OP, build_ops_from_edp_result
from qns.entity.node import QNode
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology import GridTopology, LineTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator

# 初期値
p_swap = 0.4
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数
f_req = 0.8  # 最小要求忠実度
init_fidelity = 0.99
l0_link_max = 5  # リンクレベルEPのバッファ数

s = Simulator(0, 10, 10000)

# generate network with end nodes
topo = LineTopology(
    nodes_number=5,
    nodes_apps=[
        NodeApp(p_swap=p_swap, gen_rate=gen_rate, memory_capacity=memory_capacity)
    ],
)
net = QuantumNetwork(
    topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm()
)
# create routing table and requests before controller added
net.build_route()
src = net.get_node("n1")
dest = net.get_node("n5")
net.add_request(src=src, dest=dest)
# add a controller node
controller_node = QNode(
    name="controller",
    apps=[ControllerApp(p_swap=p_swap, f_req=f_req, gen_rate=gen_rate)],
)
net.add_node(controller_node)

net.install(s)

cnode = net.get_node(name="controller")
for i in range(len(cnode.apps[0].requests)):
    print("swap_plan", i, ": ", cnode.apps[0].requests[i].swap_plan)
