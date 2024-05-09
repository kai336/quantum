from typing import Optional
from qns.network.protocol.entanglement_distribution import EntanglementDistributionApp
from qns.entity.node.node import QNode
from qns.simulator.simulator import Simulator
from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.simulator import Event, func_to_event
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.network.topology import LineTopology
from qns.network.network import QuantumNetwork
from qns.entity.node.app import Application
from qns.models.qubit import Qubit
from qns.models.qubit.const import QUBIT_STATE_0, QUBIT_STATE_1, QUBIT_STATE_L, QUBIT_STATE_N, QUBIT_STATE_P, QUBIT_STATE_R


class SendApp(Application):
    #generate qubit and send it to dest via qchannel
    def __init__(self, dest: QNode, qchannel: QuantumChannel, send_rate=1000):
        super().__init__()
        self.dest = dest
        self.qchannel = qchannel
        self.send_rate = send_rate
    
    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        time_list = []
        time_list.append(simulator.ts)

        t = simulator.ts
        event = func_to_event(t, self.send_qubit)
        self._simulator.add_event(event)

    def send_qubit(self):
        qubit = Qubit(state=QUBIT_STATE_L)

        self.qchannel.send(qubit=qubit, next_hop=self.dest)

        t = self._simulator.current_time + \
            self._simulator.time(sec=1 / self.send_rate)
        
        event = func_to_event(t, self.send_qubit)
        self._simulator.add_event(event)

class RecvApp(Application):
    #receive qubit and measure
    def handle(self, node: QNode, event: Event):
        if isinstance(event, RecvQubitPacket):
            qubit = event.qubit
            qchannel = event.qchannel
            recv_time = event.t

            print(f"measure: {qubit.measure()}, qchannel: {qchannel.name}, recv_time: {recv_time}")


def main():
    s = Simulator(0, 10, accuracy=1000000)

    n1 = QNode("n1")
    n2 = QNode("n2")

    link = QuantumChannel(name="link", delay=1, bandwidth=2)

    n1.add_qchannel(link)
    n2.add_qchannel(link)

    n1.add_apps(SendApp(dest=n2, qchannel=link))
    n2.add_apps(SendApp(dest=n1, qchannel=link))

    n1.add_apps(RecvApp())
    n2.add_apps(RecvApp())

    n1.install(s)
    n2.install(s)

    s.run()



if __name__ == "__main__":
    main()

