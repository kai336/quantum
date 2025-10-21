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
from qns.models.qubit.gate import H, CNOT, X, Y
from qns.entity.operator.operator import QuantumOperator
from qns.entity.operator.event import OperateRequestEvent, OperateResponseEvent



def gate_z_and_measure(qubit: Qubit):
    # first perform Hadamard gate to the qubit, and then measure the qubit
    H(qubit=qubit)
    result = qubit.measure()
    return result


class RecvOperateApp(Application):
    def __init__(self):
        super().__init__()
        self.add_handler(self.OperateResponseEventhandler, [OperateResponseEvent], [])

    def OperateResponseEventhandler(self, node, event: Event):
        result = event.result
        assert(self._simulator.tc.sec == 0.5)
        print(result)

n1 = QNode("n1")
o1 = QuantumOperator(name="o1", node=n1, gate=gate_z_and_measure, delay=0.5)

n1.add_operator(o1)
a1 = RecvOperateApp()
n1.add_apps(a1)

s = Simulator(0, 10, 1000)
n1.install(s)

qubit = Qubit()
request = OperateRequestEvent(o1, qubits=[qubit], t=s.time(sec=0), by=n1)
s.add_event(request)

s.run()