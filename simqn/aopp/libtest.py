import importlib
import qns.network
from requests import Request
from qns.network import QuantumNetwork
from qns.network.topology import GridTopology

qns.network.Request = Request
importlib.reload(qns.network)

req = Request
print(req.canmove)


topo = GridTopology(9)
net = QuantumNetwork(topo=topo)
net.random_requests(1)
print(net.requests[0].succeed)
