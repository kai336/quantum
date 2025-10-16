from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.entity.node.node import QNode
from qns.simulator.simulator import Simulator
from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.simulator import Event
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.network.topology import LineTopology
from qns.network.network import QuantumNetwork
from qns.entity.node.app import Application
from qns.models.qubit import Qubit

time_list = []

class OppSendApp(Application):
    def __init__(self, dest: QNode, qchannel: QuantumChannel, send_rate=1000):
        super().__init__()
        self.dest = dest
        self.qchannel = qchannel
        self.send_rate = send_rate
        self.isbusy = False
    
    def install(self, node, simulator: Simulator):
        super().install(node, simulator)
        
        time_list.append(simulator.ts)

        t = simulator.ts
        event = func_to_event(t, self.send_qubit)
        self._simulator.add_event(event)
    
    def send_qubit(self):
        qubit = Qubit()
        self.qchannel.send(qubit=qubit, next_hop=self.dest)
    

topo = LineTopology(nodes_number=5, nodes_apps=[OppSendApp(send_rate=1000)])
