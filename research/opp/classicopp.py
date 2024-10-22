from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.network.network import QuantumNetwork
from qns.network.protocol.classicforward import ClassicPacketForwardApp
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.route.route import RouteImpl
from qns.network.topology.linetopo import LineTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.event import Event, func_to_event
from qns.simulator.simulator import Simulator

class OppSendApp(Application):
    def __init__(self, dest: QNode, route: RouteImpl, send_rate=1):
        super().__init__()
        self.dest = dest
        self.route = route
        self.send_rate = send_rate

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        t = simulator.ts
        event = func_to_event(t, self.send_packet, by=self)
        self._simulator.add_event(event)

    def send_packet(self):
        packet = ClassicPacket(msg=f"msg from {self.get_node()}", src=self.get_node(), dest
                               )
