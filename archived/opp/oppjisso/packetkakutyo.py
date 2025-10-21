from typing import Any, List, Optional, Union
from qns.models.core.backend import QuantumModel
from qns.models.delay.delay import DelayModel
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

#packetにdestとnext_hopを追加する.

class QC_OPP(QuantumChannel):
    def __init__(self, name: str = None, node_list: List[QNode] = [],
                 bandwidth: int = 0, delay: Union[float, DelayModel] = 0, drop_rate: float = 0,
                 max_buffer_size: int = 0, length: float = 0, decoherence_rate: Optional[float] = 0,
                 transfer_error_model_args: dict = {}):
        super().__init__(name=name, node_list=node_list, bandwidth=bandwidth, 
                         delay=delay, drop_rate=drop_rate, max_buffer_size=max_buffer_size,
                         length=length, decoherence_rate=decoherence_rate, transfer_error_model_args=transfer_error_model_args)
        
    def send(self, qubit: QuantumModel, next_hop: QNode, dest: QNode):
        if next_hop not in self.node_list:
            raise NextHopNotConnectionException

        if self.bandwidth != 0:

            if self._next_send_time <= self._simulator.current_time:
                send_time = self._simulator.current_time
            else:
                send_time = self._next_send_time

            if self.max_buffer_size != 0 and send_time > self._simulator.current_time\
               + self._simulator.time(sec=self.max_buffer_size / self.bandwidth):
                # buffer is overflow
                print(f"qchannel {self}: drop qubit {qubit} due to overflow")
                return

            self._next_send_time = send_time + self._simulator.time(sec=1 / self.bandwidth)
        else:
            send_time = self._simulator.current_time


        #  add delay
        recv_time = send_time + self._simulator.time(sec=self.delay_model.calculate())

        # operation on the qubit
        qubit.transfer_error_model(self.length, self.decoherence_rate, **self.transfer_error_model_args)
        send_event = RecvQubitPacket_OPP(t=recv_time, name=None, by=self, qchannel=self,
                                         qubit=qubit, dest=dest, next_hop=next_hop)
        self._simulator.add_event(send_event)


class NextHopNotConnectionException(Exception):
    pass

    
    
class RecvQubitPacket_OPP(RecvQubitPacket):
    def __init__(self, next_hop: QNode, t: Optional[Time] = None, qchannel: QuantumChannel = None,
                 qubit: QuantumModel = None, dest: QNode = None, name: Optional[str] = None, by: Optional[Any] = None):
        super().__init__(t=t, name=name, qchannel=qchannel, qubit=qubit, dest=dest, by=by)
        self.next_hop = next_hop



class SendApp(Application):
    #generate qubit and send it to dest via qchannel
    def __init__(self, dest: QNode, qchannel: QC_OPP, send_rate=1000):
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




n1 = QNode("n1")
n2 = QNode("n2")
n3 = QNode("n3")

l1 = QC_OPP(name="l1", bandwidth=1)
l2 = QC_OPP(name="l2", bandwidth=1)

n1.add_qchannel(l1)
n2.add_qchannel(l1)
n2.add_qchannel(l2)
n3.add_qchannel(l2)

n1.add_apps(SendApp(dest=n3, qchannel=l1))

