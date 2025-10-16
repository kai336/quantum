from typing import Dict, Optional
import uuid

from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.models.core.backend import QuantumModel
from qns.network.requests import Request
from qns.simulator.event import Event, func_to_event
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
from qns.models.epr import WernerStateEntanglement, BellStateEntanglement
from qns.simulator.ts import Time
import qns.utils.log as log
from qns.network.topology import LineTopology
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology

import logging
import numpy as np
import random

#最初はすべてのノード間でもつれ生成チャレンジ
#隣接したもつれができたらスワッピング
#linkのlifetimeを設定

fidelity = 0.8
memory_capacity = 5
memory_time = 0.1

drop_rate = 0.0 #p_genでもつれ生成の確率を管理しているので０でおｋ

lifetime = 0.1
decoherence_rate = 1 / lifetime

gen_rate = 100 # １秒あたりのもつれ生成チャレンジ回数
p_gen = 0.1 # もつれ生成成功確率

nodes_number = 7
qchannel_delay = 0.001
cchannel_delay = 0.001

class EGDistOPP_staticreq(Application):
    def __init__(self, gen_rate: int = gen_rate,
                 drop_rate: Optional[float] = drop_rate,
                 decoherence_rate: Optional[float] = decoherence_rate,
                 lifetime: Optional[float] = lifetime):
        super().__init__()
        self.gen_rate = gen_rate
        self.drop_rate = drop_rate
        self.decoherence_rate = decoherence_rate
        self.lifetime = lifetime #もつれの寿命

        self.net: QuantumNetwork = None
        self.own: QNode = None
        self.memory: QuantumMemory = None

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.own: QNode = self._node #インストール先のノード
        self.memory: QuantumMemory = self.own.memories[0] #インストール先ノードのメモリ
        self.net = self.own.network #インストール先ノードが属するネットワーク

        #リンクのもつれ生成フラグ、寿命の設定
        qchannel_list = self.net.qchannels #ネットワークにある全qcのリスト
        for qc in qchannel_list:
            qc.is_entangled = False #もつれ生成できているかどうか
            qc.born = simulator.ts

        #隣接ノードの取得
        adj_nodes = [] #隣接ノードのリスト
        adj_links = [] #接続されたリンクのリスト
        for qc in qchannel_list:
            node_list = qc.node_list
            for node in node_list:
                if(node == self.own): #qcに自分のノードがあれば接続されたリンク
                    adj_links.append(qc)

        #接続されたリンクから隣接ノードを取得
        for qc in adj_links:
            for node in qc.node_list:
                if(node != self.own):
                    adj_nodes.append(node)

        self.adj_qc = adj_links
        self.adj_nodes = adj_nodes

        #log.debug(f"{self.own}: adj channels list {adj_links}")
        #log.debug(f"{self.own}: adj nodes list {self.adj_nodes}")

        #もつれ生成ルーチンを起動
        t = simulator.ts
        event = func_to_event(t, self.eg_routine, by=self)
        self._simulator.add_event(event)


    def eg_routine(self, gen_rate: int=100):
        #１秒あたりgen_rate回隣接するノード間でもつれ生成チャレンジを行う
        tc = self._simulator.tc
        t = tc + Time(sec=1 / self.gen_rate)
        event = func_to_event(t, self.eg_routine, by=self)
        self._simulator.add_event(event) #次のイベント追加


        #lifetimeを超えたもつれを破棄
        for qc in self.adj_qc:
            if qc.is_entangled and tc.sec - qc.born.sec > self.lifetime:
                qc.is_entangled = False
                log.debug(f"{qc}: decoherenced")
        
        #隣接するノードとのもつれ生成チャレンジ
        for qc in self.adj_qc:
            if not qc.is_entangled:
                log.debug(f"{self.own} started eg challenge")
                #確率的なもつれ生成の実装
                if random.random() <= p_gen:
                    epr = WernerStateEntanglement()
                    epr_pair = epr.to_qubits()
                    self.own.memories[0].write(epr_pair[0]) #片方を自分のメモリに保存
                    #log.debug(f"{self.own}: epr generated")
                    #nexthop設定
                    if qc.node_list[0] == self.own:
                        next_hop = qc.node_list[1]
                    else:
                        next_hop = qc.node_list[0]
                    qc.send(epr_pair[1], next_hop) #もう片方を相手に送信
                    
                    #log.debug(f"{self.own}: epr sent to {next_hop}")
                    qc.is_entangled = True
                    qc.born = tc
                    log.debug(f"{self.own} <--> {next_hop} entangled")
        
    def swap_routine(self, swap_rate: int=100):
        #有効なリンクが隣接していたらswapして新たなリンクを作る
        return



#eprの動作確認
if False:
    epr = WernerStateEntanglement()
    eprs = epr.to_qubits()
    print(eprs)

    q0 = eprs[0].measure()
    q1 = eprs[1].measure()

    print(q0, ' ', q1)


#main関数
if True:
    s = Simulator(0, 1, accuracy=1000000)
    log.logger.setLevel(logging.DEBUG)
    log.install(s)

    topo = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistOPP_staticreq()],
                        qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                        cchannel_args={"delay": cchannel_delay},
                        memory_args=[{"capacity": memory_capacity}])

    net = QuantumNetwork(topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())

    net.install(s)



    s.run()