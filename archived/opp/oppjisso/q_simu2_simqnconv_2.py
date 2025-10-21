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
from qns.network.topology import LineTopology, GridTopology
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology
from qns.models.qubit.qubit import Qubit, QState

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
p_swap = 0.8 # swapping成功確率

nodes_number = 7
qchannel_delay = 0.001
cchannel_delay = 0.001

request_number = 5

class EGDistNOPP(Application):
    
    pass

class EGDistOPP(Application):
    def __init__(self,
                 p_gen: float = p_gen, p_swap: float = p_swap,
                 gen_rate: int = gen_rate,
                 drop_rate: Optional[float] = drop_rate,
                 decoherence_rate: Optional[float] = decoherence_rate,
                 lifetime: Optional[float] = lifetime):
        super().__init__()
        
        self.p_gen = p_gen
        self.p_swap = p_swap
        self.gen_rate = gen_rate
        self.drop_rate = drop_rate
        self.decoherence_rate = decoherence_rate #不要かも
        self.lifetime = lifetime #もつれの寿命

        self.net: QuantumNetwork = None
        self.own: QNode = None
        self.memory: QuantumMemory = None
           
        #self.add_handler(self.RecvQubitHandler, [RecvQubitPacket])
        
        
    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.own: QNode = self._node #インストール先のノード
        self.memory: QuantumMemory = self.own.memories[0] #インストール先ノードのメモリ
        self.net = self.own.network #インストール先ノードが属するネットワーク
        
        ts = simulator.ts
        
        #確立したリンクself.net.establishedの初期化、寿命の設定
        #requestごとに作るため配列にした方がいい？
        try:
            self.net.established
            #log.debug(f"{self.own}net.established = {self.net.established}")
        except:
            self.net.established = []
            for req in self.net.requests:
                req.succeed = False
                req.waitingtime = float('inf')
                node1 = req.src
                # dst = req.dest
                # route_result = self.net.query_route(node1, dst)
                # #log.debug(f"{route_result}")
                # node2 = route_result[0][1]
                self.net.established.append([node1, node1, ts]) #node1, node2, born
                log.debug(f"{self.own}new! net.established = {self.net.established}")


        #リンクのもつれ生成フラグ、寿命の設定
        qchannel_list = self.net.qchannels #ネットワークにある全qcのリスト
        for qc in qchannel_list:
            qc.is_entangled = False #もつれ生成できているかどうか
            qc.born = ts

        
        #もつれ生成ルーチン、スワップルーチンを起動
        event_eg = func_to_event(ts, self.eg_routine, by=self)
        event_swap = func_to_event(ts, self.swap_routine, by=self)
        self._simulator.add_event(event_eg)
        self._simulator.add_event(event_swap)
        
        self.get_adjacent()
    

    def est_init(self, idx: int):
        #established linkの初期化
        tc = self._simulator.tc
        node1 = self.net.requests[idx].src
        # dst = self.net.requests[idx].dest
        # route_result = self.net.query_route(node1, dst)
        # node2 = route_result[0][1]
        self.net.established[idx] = [node1, node1, tc]
        
    
    def get_adjacent(self):
        #隣接リンクの取得
        qchannel_list = self.net.qchannels #ネットワークにある全qcのリスト
        adj_qc = [] #接続されたリンクのリスト
        for qc in qchannel_list:
            node_list = qc.node_list
            for node in node_list:
                if(node == self.own): #qcに自分のノードがあれば接続されたリンク
                    adj_qc.append(qc)

        self.adj_qc = adj_qc

        # log.debug(f"{self.own}: adj channels list {adj_links}")


    def eg_routine(self, gen_rate: int=100):
        #１秒あたりgen_rate回隣接するノード間でもつれ生成チャレンジを行う　生成できたらストップ
        tc = self._simulator.tc
        t = tc + Time(sec=1 / self.gen_rate)
        event = func_to_event(t, self.eg_routine, by=self)
        self._simulator.add_event(event) #次のイベント追加

        #self.get_adjacent()

        #lifetimeを超えたもつれを破棄 established linkを含む
        for qc in self.adj_qc:
            if qc.is_entangled and tc.sec - qc.born.sec > self.lifetime:
                qc.is_entangled = False
                log.debug(f"[eg_routine]{qc}: born {qc.born.sec}s, now {tc.sec}s --->decoherenced")
        #established linkは初期化される
        for i in range(len(self.net.established)):
            if tc.sec - self.net.established[i][2].sec > self.lifetime:
                self.est_init(i)
                log.debug(f"lost established")
                
        
        #隣接するノードとのもつれ生成チャレンジ
        for qc in self.adj_qc:
            if not qc.is_entangled:
                #log.debug(f"[eg_routine]{self.own} started eg challenge")
                #確率的なもつれ生成の実装
                if random.random() < p_gen:
                    epr = WernerStateEntanglement()
                    #log.debug(f"{self.own}: epr generated")
                    #nexthop設定
                    if qc.node_list[0] == self.own:
                        next_hop = qc.node_list[1]
                    else:
                        next_hop = qc.node_list[0]
                    qc.send(epr, next_hop) #もう片方を相手に送信
                    
                    #log.debug(f"{self.own}: epr sent to {next_hop}")
                    qc.is_entangled = True
                    qc.born = tc
                    log.debug(f"[eg_routine]{self.own} <--> {next_hop} entangled")


    def swap_routine(self, swap_rate: int=100):
        tc = self._simulator.tc
        t = tc + Time(sec=1 / self.gen_rate)
        event = func_to_event(t, self.swap_routine, by=self)
        self._simulator.add_event(event) #次のイベント追加
        
        #現在確立できているリンクに、有効なリンクが隣接していたらswapして新たなリンクを作る
        #自分がリンクの先端ならnexthopとswap
        isallfinished = True
        for i in range(len(self.net.requests)): #i番目のリクエストについて
            if not self.net.requests[i].succeed:
                isallfinished = False
                node2 = self.net.established[i][1]
                if node2 == self.own: #自分がリンクの最先端なら隣接リンクとswap
                    dest = self.net.requests[i].dest
                    route_result = self.net.route.query(src=self.own, dest=dest)
                    try:
                        next_hop = route_result[0][1]
                        for qc in self.adj_qc:
                            if (qc.node_list[0] == next_hop or qc.node_list[1] == next_hop) and qc.is_entangled:
                                if random.random() < p_swap: #確率的swapping
                                    if next_hop == self.net.requests[i].dest: #次のスワップでリクエストが完了するとき
                                        qc.is_entangled = False
                                        self.net.established[i][1] = next_hop
                                        self.net.requests[i].succeed = True
                                        self.net.requests[i].waitingtime = tc.sec
                                        log.debug(f"[swap_routine]{self.own} completed! {self.net.established[i]} req {i} {self.net.requests[i]}")
                                    else:
                                        qc.is_entangled = False
                                        self.net.established
                                        self.net.established[i][1] = next_hop
                                        self.net.established[i][2] = tc
                                        log.debug(f"[swap_routine]{self.own} new! established[{i}] {self.net.established[i]}")
                                else:
                                    self.est_init(i)
                                    qc.is_entangled = False
                    except IndexError:
                        raise Exception("Route error")
        
        if isallfinished:
            log.debug(f"all requests finished!!")
            self._simulator.event_pool.event_list.clear()
        


    # def RecvQubitHandler(self, node: QNode, event: Event):
    #     #送られてきたもつれ対の片方を保存
    #     if isinstance(event, RecvQubitPacket):
    #         qubit = event.qubit
    #         self.memory.write(qubit)
            
    # def RecvClassicPacketHander(self, node: QNode, event: Event):
    #     #swapリクエスト受信から実行まで
    #     return
        




#eprの動作確認
if False:
    epr = WernerStateEntanglement()
    eprs = epr.to_qubits()
    print(eprs)

    q0 = eprs[0].measure()
    q1 = eprs[1].measure()

    print(q0, ' ', q1)

#metrics = [pgen, pswap, L, N, M, k]
#L = lifetime, N = the number of requests, M = the size of grid, k = the opportunism degree
#7nodes linetopo, req=[n1->n7], number of req = 4
def exp1(islog: bool = False):
    s = Simulator(0, 10, accuracy=1000000)
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)

    topo1 = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistOPP()],
                        qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                        cchannel_args={"delay": cchannel_delay},
                        memory_args=[{"capacity": memory_capacity}])

    net = QuantumNetwork(topo=topo1, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()
    
    n1 = net.get_node('n1')
    n7 = net.get_node('n7')
    
    for i in range(request_number):
        net.add_request(src=n1, dest=n7)
        
    log.debug(f"{net.requests}")
    
    net.install(s)

    s.run()
    
    waitingtime = [req.waitingtime for req in net.requests]
    print(waitingtime)
    return waitingtime


#7nodes linetopo, random req, number of reqs = 4
def exp2(islog: bool = False):
    s = Simulator(0, 1, accuracy=1000000)
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)

    topo1 = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistOPP()],
                        qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                        cchannel_args={"delay": cchannel_delay},
                        memory_args=[{"capacity": memory_capacity}])
    
    net = QuantumNetwork(topo=topo1, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()
    
    net.random_requests(number=4, allow_overlay=True)
    
    log.debug(f"{net.requests}")
    
    net.install(s)

    s.run()
    waitingtime = [req.waitingtime for req in net.requests]
    print(waitingtime)


#4*4grid, random req, number of reqs = 4
def exp3(islog: bool = False):
    s = Simulator(0, 1, accuracy=1000000)
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)
    
    topo2 = GridTopology(nodes_number=16, nodes_apps=[EGDistOPP()],
                         qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                         cchannel_args={"delay": cchannel_delay},
                         memory_args=[{"capacity": memory_capacity}])

    net = QuantumNetwork(topo=topo2, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()
    
    net.random_requests(number=4)
    
    log.debug(f"{net.requests}")
    
    net.install(s)

    s.run()
    
    waitingtime = [req.waitingtime for req in net.requests]
    print(waitingtime)



if False:
    s = Simulator(0, 1, accuracy=1000000)
    islog: bool = True
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)

    topo1 = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistOPP()],
                        qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                        cchannel_args={"delay": cchannel_delay},
                        memory_args=[{"capacity": memory_capacity}])

    topo2 = GridTopology(nodes_number=16, nodes_apps=[EGDistOPP()],
                            qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                            cchannel_args={"delay": cchannel_delay},
                            memory_args=[{"capacity": memory_capacity}])

    net = QuantumNetwork(topo=topo2, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()

    n1 = net.get_node('n1')
    n7 = net.get_node('n7')

    net.random_requests(number=4)
    log.debug(f"{net.requests}")

    # for i in range(request_number):
    #     net.add_request(src=n1, dest=n7)

    net.install(s)

    s.run()


exp1res = []
for i in range(10):
    exp1res =  exp1res + exp1()
    
avarage_waitingtime = sum(exp1res)/float(len(exp1res))
print(avarage_waitingtime)


