from typing import Any, Optional
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

from qns.models.epr import BellStateEntanglement
from qns.entity.memory.memory import QuantumMemory
from qns.simulator.ts import Time

# e1 = BellStateEntanglement(fidelity=0.8, name="e1")

# # change BellStateEntanglement model to Qubit model
# q0, q1 = e1.to_qubits()
# print(q0.state)
# print(q1.state)

# # execute teleportation protocol to transmit a Qubit
# q0 = Qubit(QUBIT_STATE_0) # the transmitting qubit
# e0 = BellStateEntanglement(fidelity=0.8, name="e0")

# q2 = e0.teleportion(q0) # The transmitted qubit
# print(q2.measure())
# assert(q2.measure() == 0)

class TeleportationApp(Application):
    def __init__(self, dest: QNode, send_rate=1):
        super().__init__()
        self.dest = dest
        self.send_rate = send_rate

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)

        t = simulator.ts
        event = func_to_event(t, self.teleport, by=self)
        self._simulator.add_event(event)

    def teleport(self):
        q_src = Qubit(QUBIT_STATE_0)
        print(self.get_node(), ": QUBIT_STATE_0 generated", end=', ')
        e = BellStateEntanglement(fidelity=0.8, name="e")
        dest_mem = self.dest.get_memory(memory=0)
        q_dst = e.teleportion(q_src)
        q_dst.name = 'q_dst' #メモリから読み出すときのキーワード
        dest_mem.write(q_dst)
        print(self.dest, ": QUBIT saved")
        t = self._simulator.current_time + \
            self._simulator.time(sec=1 / self.send_rate)
        recv_time = t #+ self._simulator.time(sec=self.delay_model.calculate())
        #送信先の受信イベント
        send_event = RecvQubitPacket(recv_time, dest=self.dest, by=self, qubit=q_dst)
        #次の送信イベント
        event = func_to_event(t, self.teleport)
        self._simulator.add_event(send_event)
        self._simulator.add_event(event)

class RecvTPApp(Application):
    def handle(self, node: QNode, event: Event):
        if isinstance(event, RecvQubitPacket):
            mem = event.dest.memories[0]
            qubit = mem.read("q_dst")
            recv_time = event.t

            print(f"measure: {qubit.measure()}, recv_time: {recv_time}")

class RecvEvent(Event):
    def __init__(self, t: Time, name: str, by=None, dest: QNode):
        super().__init__(t, name, by)
        self.dest = dest
    def invoke(self):
        self.dest.handle(self)

# #量子メモリ
# n1 = QNode("n1")
# m = QuantumMemory("m1")
# n1.add_memory(m)
# print(n1.memories)
# print(n1.memories[0])

n1 = QNode("n1")
n2 = QNode("n2")
m1 = QuantumMemory("m1")
m2 = QuantumMemory("m2")
n1.add_memory(m1)
n2.add_memory(m2)

link = QuantumChannel("link")

n1.add_apps(TeleportationApp(dest=n2))
# n1.add_apps(RecvTPApp())
# n2.add_apps(TeleportationApp(dest=n1))
n2.add_apps(RecvTPApp())

s = Simulator(0, 10, 1000000)

n1.install(s)
n2.install(s)

s.run()