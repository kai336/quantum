from qns.network.topology.topo import ClassicTopology
from edp.alg.edp import qnet2DictConverter
from qns.network import QuantumNetwork
from qns.network.topology import GridTopology

topo = GridTopology(nodes_number=9)
net = QuantumNetwork(topo=topo, classic_topo=ClassicTopology.All)
qchannels = net.qchannels
converted = qnet2DictConverter(qchannels, gen_rate=50)
print(converted)
