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
from qns.network.requests import Request
from qns.models.epr import BellStateEntanglement
from qns.entity.memory.memory import QuantumMemory
from qns.simulator.ts import Time
from qns.network.topology.topo import ClassicTopology
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from typing import Dict, Optional
import uuid
from qns.models.epr import WernerStateEntanglement
import qns.utils.log as log

#net.requestsからパケットのsrc, destを設定するためtransmitクラス
from qns.network.protocol.entanglement_distribution import Transmit


#全部入りのアプリケーション
#EntanglementDistributionAppをベースに作る


# handlerにパケット転送を定義.
# next_hopへのアクセス
# 1.実行中のnet.requestからdest情報を入手
# 2.query_res = net.query_route(self.getnode(), dest)
# 3.next_hop = query_res[0][1]
# qchannel.send(qubit=qubit, next_hop=next_hop)

class QubitDistApp_OPP(Application):
    def __init__(self, send_rate: Optional[int] = None):
        super().__init__()
        self.net: QuantumNetwork = None # 属するネットワーク
        self.own: QNode = None # インストールされているノード
        self.memory: QuantumMemory = None # ノードがもつメモリ
        self.src: Optional[QNode] = None # 受信リクエストのときの、送信元
        self.dst: Optional[QNode] = None # 送信リクエストのときの、宛先
        self.send_rate: int = send_rate
        self.send_count = 0

        # idでリクエスト管理
        self.state: Dict[str, Transmit] = {}
        
        # handlerを設定
        self.add_handler(self.RecvQubitHander, [RecvQubitPacket])

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.own: QNode = self._node
        self.memory: QuantumMemory = self.own.memories[0]
        self.net = self.own.network
        try:
            request: Request = self.own.requests[0]
            if self.own == request.src:
                self.dst = request.dest
            elif self.own == request.dest:
                self.src = request.src
            self.send_rate = request.attr.get("send_rate")
        except IndexError:
            pass

        if self.dst is not None:
            # I am a sender
            t = simulator.ts
            event = func_to_event(t, self.new_distribution, by=self)
            self._simulator.add_event(event)

    def RecvQubitHander(self, node: QNode, event: Event):
        self.handler(event)

    def RecvClassicPacketHandler(self, node: QNode, event: Event):
        self.handle_response(event)

    def new_distribution(self):
        return

    def request_distribution(self, transmit_id: str):
        return

    def handle_response(self, packet: RecvClassicPacket):
        return
    
    def generate_qubit(self, src: QNode, dst: QNode, transmit_id: Optional[str] = None) -> QuantumModel:
        return
    
    def set_first_epr(self, epr: QuantumModel, transmit_id: str):
        return
    
    def set_second_epr(self, epr: QuantumModel, transmit_id: str):
        return

    #def handler(self, packet: RecvQubitPacket):
        # self._node == dest なら受信完了
        # else next_hopに中継

def main():
    s = Simulator(0, 10, accuracy=1000000)

    nodes_number = 15 # the number of nodes
    qchannel_delay = 0.05 # the delay of quantum channels
    cchannel_delay = 0.05 # the delay of classic channels
    memory_capacity = 50 # the size of quantum memories
    send_rate = 10 # the send rate
    requests_number = 5 # the number of sessions (SD-pairs)


    #build topo -> build network -> build routingtable -> generate requests -> install -> s.run

    topo = LineTopology(nodes_number=nodes_number,
        qchannel_args={"delay": qchannel_delay},
        cchannel_args={"delay": cchannel_delay},
        memory_args=[{"capacity": memory_capacity}],
        nodes_apps=[])
    
    net = QuantumNetwork(topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm)
    net.build_route()
    n1 = net.get_node('n1')
    n5 = net.get_node('n5')

    net.add_request(src=n1, dest=n5)
    net.add_request(src=n5, dest=n1)

    net.install(s)

    s.run()



if __name__ == "__main__":
    main()

