from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.entity.node.node import QNode
from qns.simulator.simulator import Simulator
from qns.entity.cchannel.cchannel import (
    ClassicChannel,
    ClassicPacket,
    RecvClassicPacket,
)
from qns.simulator import Event

app = EntanglementDistributionApp()  # the application
n1 = QNode("n1")

# add an application
n1.add_apps(app)

# get applications by the class
assert app == n1.get_apps(EntanglementDistributionApp)[0]

# install application when generate the quantum node
n2 = QNode("n2", apps=[EntanglementDistributionApp()])


from qns.entity.node.app import Application


class PrintApp(Application):
    def __init__(self):
        super().__init__()

    def install(self, node, simulator: Simulator):
        # initiate the application
        super().install(node, simulator)
        print("initiate app")

        # RecvClassicPacketHandler should handle classic packets from node n2
        self.add_handler(RecvClassicPacketHandler, [RecvClassicPacket], [n1, n2])
        print("init")

    def RecvClassicPacketHandler(self, node: QNode, event: Event):
        packet = event.packet
        msg = packet.get()
        print(f"{node} recv packet: {msg} from {packet.src}->{packet.dest}")
        return True  # bypass the following applications
