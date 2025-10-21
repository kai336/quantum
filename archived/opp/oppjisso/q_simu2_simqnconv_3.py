from typing import Dict, Optional, List
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

lifetime = 30
decoherence_rate = 1 / lifetime

gen_rate = 1 # １秒あたりのもつれ生成チャレンジ回数

p_gen = 0.1 # もつれ生成成功確率
p_swap = 0.8 # swapping成功確率

nodes_number = 7
qchannel_delay = 0.0
cchannel_delay = 0.0

request_number = 5

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
        self.drop_rate = drop_rate #不要
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
            self.net.runtime = ts.sec
            self.net.established = []
            for req in self.net.requests:
                req.succeed = False
                req.waitingtime = float('inf') #不要
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
            qc.is_reserved = False
            qc.reservation = -1 #idx of req
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
        log.debug(f"[est_init] {self.own} req {idx} {self.net.requests[idx]} lost established link")
        
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
        
    def get_qc(self, src: QNode, dest: QNode) -> QuantumChannel:
        apps = src.get_apps(EGDistOPP)
        app = apps[0]
        for qc in app.adj_qc:
            if qc.node_list[0] == dest or qc.node_list[1] == dest:
                return qc
            
        raise Exception("No qc found")
    
    def get_route_nodes(self, src: QNode, dest: QNode) -> List[QNode]:
        route_result = self.net.route.query(src=src, dest=dest)
        try:
            return route_result[0][2]
        except IndexError:
            log.debug(f"[get_route_nodes] {self.own} no route found: src={src}, dest={dest}")
            raise Exception("No route found")
    
    def get_routes(self, src: QNode, dest: QNode):
        route_result = self.net.route.query(src=src, dest=dest)
        try:
            routes = []
            for route_tuple in route_result:
                routes.append(route_tuple[2])
            log.debug(f"[get_routes] {routes}")
            return routes
        except IndexError:
            log.debug(f"[get_route_nodes] {self.own} no route found: src={src}, dest={dest}")
            raise Exception("No route found")

    def opp_swapping(self, src: QNode, dest: QNode, idx: int): 
        #進めるところまでswapping
        #k-oppの実装にも使えそう
        tc = self._simulator.tc
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        for i in range(len(route_nodes)-1):
            qc = self.get_qc(route_nodes[i], route_nodes[i+1])
            next_hop = route_nodes[i+1]
            if qc.is_entangled:
                qc.is_entangled = False
                if random.random() < self.p_swap: #swap成功
                    #perform swap
                    self.net.established[idx][1] = next_hop
                    self.net.established[idx][2] = tc
                    if not next_hop == dest:
                        #continue swapping
                        log.debug(f"[opp_swapping]{self.own} req {idx} {self.net.requests[idx]} new! established link {self.net.established[idx]}")
                    else:
                        #complete the request
                        self.net.requests[idx].succeed = True
                        self.net.requests[idx].waitingtime = tc.sec
                        log.debug(f"[opp_swapping]{self.own} req {idx} {self.net.requests[idx]} completed! {self.net.established[idx]}")
                else: #swap失敗
                    log.debug(f"[opp_swapping] req {idx} failed to swap {route_nodes[i]} <-> {route_nodes[i+1]}")
                    self.est_init(idx)
                    
            else:
                break #これ以上進めない
        

    def eg_routine(self):
        #every time slotにおいて隣接するノード間でもつれ生成チャレンジを行う　生成できたらストップ
        tc = self._simulator.tc
        t = tc + Time(sec=1 / self.gen_rate)
        event = func_to_event(t, self.eg_routine, by=self)
        self._simulator.add_event(event) #次のtime slotにイベント追加

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
                
        
        #隣接するノードとのもつれ生成チャレンジ
        for qc in self.adj_qc:
            if not qc.is_entangled:
                #log.debug(f"[eg_routine]{self.own} started eg challenge")
                #確率的なもつれ生成の実装
                if random.random() < self.p_gen:
                    # epr = WernerStateEntanglement()
                    # #log.debug(f"{self.own}: epr generated")
                    # #nexthop設定
                    if qc.node_list[0] == self.own: #1つのqcに対して二重にチャレンジを行うのを防ぐ
                        next_hop = qc.node_list[1]
                        qc.is_entangled = True
                        qc.born = tc
                        log.debug(f"[eg_routine]{self.own} <--> {next_hop} entangled")
                    else:
                        pass
                    


    def swap_routine(self):
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
                if node2 == self.own: #自分がリンクの最先端ならswapチャレンジ
                    dest = self.net.requests[i].dest
                    self.opp_swapping(src=self.own, dest=dest, idx=i)
        
        if isallfinished:
            self.net.runtime = tc.sec
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
        

class EGDistNOPP(EGDistOPP):
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
        self.drop_rate = drop_rate #不要
        self.decoherence_rate = decoherence_rate #不要かも
        self.lifetime = lifetime #もつれの寿命
        self.net: QuantumNetwork = None
        self.own: QNode = None
        self.memory: QuantumMemory = None
        
    def get_qc(self, src: QNode, dest: QNode) -> QuantumChannel:
        apps = src.get_apps(EGDistNOPP)
        app = apps[0]
        for qc in app.adj_qc:
            if qc.node_list[0] == dest or qc.node_list[1] == dest:
                return qc
            
        raise Exception("No qc found")
    
    def isallready(self, src: QNode, dest: QNode) -> bool:
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        allready = True
        for i in range(len(route_nodes)-1):
            qc = self.get_qc(route_nodes[i], route_nodes[i+1])
            if not qc.is_entangled:
                allready = False
                break
        return allready
            
    def nopp_swapping(self, src: QNode, dest: QNode, idx: int):
        if not self.isallready(src, dest):
            pass
        else: #すべてのリンクでもつれ生成できていたら順番にswapping
            tc = self._simulator.tc
            route_nodes = self.get_route_nodes(src=src, dest=dest)
            for i in range(len(route_nodes)-1):
                qc = self.get_qc(route_nodes[i], route_nodes[i+1])
                qc.is_entangled = False
                next_hop = route_nodes[i+1]
                if random.random() < self.p_swap: #swap成功
                    self.net.established[idx][1] = next_hop
                    self.net.established[idx][2] = tc
                    if not next_hop == dest:
                        #continue swapping
                        log.debug(f"[nopp_swapping] {self.own} req {idx} {self.net.requests[idx]} new! established link {self.net.established[idx]}")
                    else:
                        #complete the request
                        self.net.requests[idx].succeed = True
                        self.net.requests[idx].waitingtime = tc.sec
                        log.debug(f"[nopp_swapping]{self.own} req {idx} {self.net.requests[idx]} completed! {self.net.established[idx]}")
                else: #swap失敗
                    log.debug(f"[nopp_swapping] req {idx} {self.net.requests[idx]} failed to swap {route_nodes[i]} <-> {route_nodes[i+1]}")
                    self.est_init(idx)
                    break
        
    
    def swap_routine(self, swap_rate: int=1):
        tc = self._simulator.tc
        t = tc + Time(sec=1 / self.gen_rate)
        event = func_to_event(t, self.swap_routine, by=self)
        self._simulator.add_event(event) #次のイベント追加
        
        isallfinished = True
        for i in range(len(self.net.requests)): #i番目のリクエストについて
            if not self.net.requests[i].succeed:
                isallfinished = False
                src = self.net.requests[i].src
                if src == self.own: #自分がリクエスト送信元なら経路のリンクが全て有効になるとswapping
                    dest = self.net.requests[i].dest
                    self.nopp_swapping(src=src, dest=dest, idx=i)
        
        if isallfinished:
            self.net.runtime = tc.sec
            log.debug(f"all requests finished!!")
            self._simulator.event_pool.event_list.clear()
        


#metrics = [pgen, pswap, L, N, M, k]
#L = lifetime, N = the number of requests, M = the size of grid, k = the opportunism degree
#7nodes linetopo, req=[n1->n7], number of req = 4
def exp1(islog: bool = False, isopp: bool = False):
    s = Simulator(0, 1000000, accuracy=1)
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)
    
    if isopp:
        topo1 = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistOPP()],
                            qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                            cchannel_args={"delay": cchannel_delay},
                            memory_args=[{"capacity": memory_capacity}])
    else:
        topo1 = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistNOPP()],
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
    return waitingtime


#7nodes linetopo, random req, number of reqs = 4
def exp2(islog: bool = False, isopp: bool = False):
    s = Simulator(0, 10, accuracy=1000000)
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)

    if isopp:
        topo1 = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistOPP()],
                            qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                            cchannel_args={"delay": cchannel_delay},
                            memory_args=[{"capacity": memory_capacity}])
    else:
        topo1 = LineTopology(nodes_number=nodes_number, nodes_apps=[EGDistNOPP()],
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
    return waitingtime


def set_seed(seed:int = None):
    random.seed(seed)
    np.random.seed(seed=seed)


#4*4grid, random req, number of reqs = 4
size_of_grid = 4
def exp3(islog: bool = False, isopp: bool = False,
         p_gen: float = p_gen, p_swap: float = p_swap,
         L: float = lifetime, N: int = request_number, M: int = size_of_grid, seed: int = None):
    s = Simulator(0, 1000000, accuracy=1)
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)
    drop_rate = 0.0
    if isopp:
        topo2 = GridTopology(nodes_number=M**2, nodes_apps=[EGDistOPP(p_gen=p_gen, p_swap=p_swap, lifetime=L)],
                         qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                         cchannel_args={"delay": cchannel_delay},
                         memory_args=[{"capacity": memory_capacity}])
    else:
        topo2 = GridTopology(nodes_number=M**2, nodes_apps=[EGDistNOPP(p_gen=p_gen, p_swap=p_swap, lifetime=L)],
                         qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                         cchannel_args={"delay": cchannel_delay},
                         memory_args=[{"capacity": memory_capacity}])

    net = QuantumNetwork(topo=topo2, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()
    
    set_seed(seed)
    net.random_requests(number=N, allow_overlay=True)
    set_seed(None)
    
    
    log.debug(f"{net.requests}")
    
    net.install(s)
    s.run()
    totalwaitingtime = net.runtime
    #print(p_gen, waitingtime)
    return totalwaitingtime

exp3(islog=True, isopp=True)

def totalwaitingtimecheck():
    print(exp3(N=20)/20)

#totalwaitingtimecheck()

def linkgadabuttenaikacheck():
    s = Simulator(0, 100000, accuracy=1)
    islog: bool = True
    if islog:
        log.logger.setLevel(logging.DEBUG)
        log.install(s)

    topo1 = LineTopology(nodes_number=7, nodes_apps=[EGDistOPP(p_swap=1, p_gen=1)],
                        qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                        cchannel_args={"delay": cchannel_delay},
                        memory_args=[{"capacity": memory_capacity}])

    topo2 = GridTopology(nodes_number=16, nodes_apps=[EGDistOPP()],
                            qchannel_args={"drop_rate": drop_rate, "delay": qchannel_delay},
                            cchannel_args={"delay": cchannel_delay},
                            memory_args=[{"capacity": memory_capacity}])

    net = QuantumNetwork(topo=topo1, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()

    n1 = net.get_node('n1')
    n2 = net.get_node('n2')
    n6 = net.get_node('n6')
    n7 = net.get_node('n7')

    net.add_request(src=n1, dest=n7)
    net.add_request(src=n2, dest=n6)
    log.debug(f"{net.requests}")

    net.install(s)

    s.run()
    
    #[0.0] [<Request <node n1>-><node n7>>, <Request <node n2>-><node n6>>]
    # [0.0] <node n1>new! net.established = [[<node n1>, <node n1>, 0.0]]
    # [0.0] <node n1>new! net.established = [[<node n1>, <node n1>, 0.0], [<node n2>, <node n2>, 0.0]]
    # [0.0] simulation started.
    # [0.0] [eg_routine]<node n1> <--> <node n2> entangled
    # [0.0] [eg_routine]<node n2> <--> <node n3> entangled
    # [0.0] [eg_routine]<node n4> <--> <node n3> entangled
    # [0.0] [eg_routine]<node n4> <--> <node n5> entangled
    # [0.0] [eg_routine]<node n7> <--> <node n6> entangled
    # [0.0] [swap_routine]<node n1> new! established[0] [<node n1>, <node n2>, 0.0]
    # [0.0] [eg_routine]<node n6> <--> <node n5> entangled
    # [0.0] [swap_routine]<node n2> new! established[0] [<node n1>, <node n3>, 0.0]
    # [1.0] [eg_routine]<node n2> <--> <node n1> entangled
    # [1.0] [eg_routine]<node n2> <--> <node n3> entangled
    # [1.0] [swap_routine]<node n3> new! established[0] [<node n1>, <node n4>, 1.0]
    # [1.0] [swap_routine]<node n2> new! established[1] [<node n2>, <node n3>, 1.0]
    # [1.0] [eg_routine]<node n3> <--> <node n2> entangled
    # [1.0] [eg_routine]<node n3> <--> <node n4> entangled
    # [2.0] [swap_routine]<node n4> new! established[0] [<node n1>, <node n5>, 2.0]
    # [2.0] [eg_routine]<node n5> <--> <node n4> entangled
    # [2.0] [swap_routine]<node n3> new! established[1] [<node n2>, <node n4>, 2.0]
    # [3.0] [eg_routine]<node n4> <--> <node n3> entangled
    # [3.0] [swap_routine]<node n5> new! established[0] [<node n1>, <node n6>, 3.0]
    # [3.0] [swap_routine]<node n4> new! established[1] [<node n2>, <node n5>, 3.0]
    # [3.0] [swap_routine]<node n6> completed! [<node n1>, <node n7>, 3.0] req 0 <Request <node n1>-><node n7>>
    # [4.0] [eg_routine]<node n4> <--> <node n5> entangled
    # [4.0] [eg_routine]<node n6> <--> <node n5> entangled
    # [4.0] [eg_routine]<node n6> <--> <node n7> entangled
    # [4.0] [swap_routine]<node n5> completed! [<node n2>, <node n6>, 3.0] req 1 <Request <node n2>-><node n6>>
    # [4.0] all requests finished!!
    #Linkをだぶることはなく正常に動いている


#main experiment
def exp4():
    import time
    start = time.time()
    M = 5
    N = 20
    L = 6
    p_swap = 0.8

    p_gens = np.linspace(0.1, 1.0, 10)
    avarage_nopp = []
    avarage_opp = []
    for p in p_gens:
        totalwaitings_nopp = []
        totalwaitings_opp = []
        for seed in range(5):
            for i in range(10):
                waitingtime_nopp = exp3(isopp=False, p_gen=p, p_swap=p_swap, L=L, N=N, M=M, seed=seed)
                totalwaitings_nopp.append(waitingtime_nopp)
                waitingtime_opp = exp3(isopp=True, p_gen=p, p_swap=p_swap, L=L, N=N, M=M, seed=seed)
                totalwaitings_opp.append(waitingtime_opp)
                print(seed, p, i, 'res', waitingtime_nopp, waitingtime_opp)
        avarage_waitingtime_nopp = sum(totalwaitings_nopp) / len(totalwaitings_nopp)
        avarage_waitingtime_opp = sum(totalwaitings_opp) / len(totalwaitings_opp)
        avarage_nopp.append(avarage_waitingtime_nopp)
        avarage_opp.append(avarage_waitingtime_opp)

    end = time.time()
    time_diff = end - start

    print(avarage_nopp)
    print(avarage_opp)
    print(time_diff)
    
    
#print(exp3(islog=True, isopp=False))
#print(exp3(islog=True, isopp=True))