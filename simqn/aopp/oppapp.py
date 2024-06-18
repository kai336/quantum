import random
import uuid
import importlib
from typing import Dict, Optional, List
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.models.delay.delay import DelayModel
from qns.simulator.ts import Time
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
import qns.utils.log as log
import qns.network
from requests import Request
from qchannel import QuantumChannel

qns.network.Request = Request
importlib.reload(qns.network)




FIDELITY = 0.8
MEMORY_CAPACITY = 5
MEMORY_TIME = 0.1

DROP_RATE = 0.0 #p_genでもつれ生成の確率を管理しているので０でok

LIFETIME = 30
DECOHERENCE_RATE = 1 / LIFETIME

GEN_RATE = 1 # １秒あたりのもつれ生成チャレンジ回数

P_GEN = 0.1 # もつれ生成成功確率
P_SWAP = 0.8 # swapping成功確率

NODES_NUMBER = 7
QCHANNEL_DELAY = 0.0
CCHANNEL_DELAY = 0.0

REQUESTs_NUMBER = 5

M = 5
N = 20
L = 6
P_SWAP = 0.8

#todo: recreate this app
#override class: QuantumChannel, Request, QuantumNetwork
#
#replace established -> list of qc

def make_qc(src: QNode, dest: QNode, born: Time):
    #build a quantum channel between src<->dest
    return QuantumChannel(name=uuid.uuid4().__str__(), node_list=[src, dest], born=born)

class OpportunistcApp(Application):
    def __init__(self,
                 p_gen: float = P_GEN, p_swap: float = P_SWAP,
                 gen_rate: int = GEN_RATE,
                 drop_rate: Optional[float] = DROP_RATE,
                 decoherence_rate: Optional[float] = DECOHERENCE_RATE,
                 lifetime: Optional[float] = LIFETIME,
                 isopp: bool = False,
                 alpha: float = 0):
        super().__init__()
        
        self.p_gen = p_gen
        self.p_swap = p_swap
        self.gen_rate = gen_rate
        self.drop_rate = drop_rate #不要
        self.decoherence_rate = decoherence_rate #不要かも
        self.lifetime = lifetime #もつれの寿命
        self.isopp = isopp
        self.alpha = alpha

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
        except AttributeError:
            self.net.runtime = ts.sec
            self.net.established = []
            for req in self.net.requests:
                req.canmove = False
                req.pos :int = 0
                req.succeed = False
                req.waitingtime = float('inf') #不要?
                src = req.src
                # dst = req.dest
                # route_result = self.net.query_route(node1, dst)
                # #log.debug(f"{route_result}")
                # node2 = route_result[0][1]
                self.net.established.append([src, src, ts]) #node1, node2, born
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
        src = self.net.requests[idx].src
        dest = self.net.requests[idx].dest
        self.net.requests[idx].pos = 0
        self.net.requests[idx].canmove = False
        # dst = self.net.requests[idx].dest
        # route_result = self.net.query_route(node1, dst)
        # node2 = route_result[0][1]
        self.net.established[idx] = [src, src, tc]
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        self.releaselinks(route_nodes=route_nodes)
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
        apps = src.get_apps(OpportunistcApp)
        app = apps[0]
        for qc in app.adj_qc:
            if qc.node_list[0] == dest or qc.node_list[1] == dest:
                return qc
            
        raise Exception("No qc found")
    
    def get_route_nodes(self, src: QNode, dest: QNode) -> List[QNode]:
        #経路を１つ取得
        route_result = self.net.route.query(src=src, dest=dest)
        try:
            return route_result[0][2]
        except IndexError:
            log.debug(f"[get_route_nodes] {self.own} no route found: src={src}, dest={dest}")
            raise Exception("No route found")
    
    def get_routes(self, src: QNode, dest: QNode):
        #経路を取得
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
    
    def isallready(self, src: QNode, dest: QNode) -> bool:
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        allready = True
        for i in range(len(route_nodes)-1):
            qc = self.get_qc(route_nodes[i], route_nodes[i+1])
            if not qc.is_entangled:
                allready = False
                break
        return allready
        
    def reserve_nopp(self, src: QNode, dest: QNode, idx: int):
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        isallready = True
        #すべて有効か
        for i in range(len(route_nodes)-1):
            qc = self.get_qc(route_nodes[i], route_nodes[i+1])
            if qc.is_entangled and (not qc.is_reserved or qc.reservation == idx): #有効かつ(予約されていないor自分が予約している)
                pass
            else:
                isallready = False
                break
        
        if isallready:
            self.net.requests[idx].canmove = True
            for i in range(len(route_nodes)-1):
                qc = self.get_qc(route_nodes[i], route_nodes[i+1])
                qc.is_reserved = True
                qc.reservation = idx

    def reserve_opp(self, src: QNode, dest: QNode, idx: int):
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        #進めるところまで予約 k-oppの場合
        pos = self.net.requests[idx].pos
        for i in range(pos, len(route_nodes)-1):
            qc = self.get_qc(route_nodes[i], route_nodes[i+1])
            if qc.is_entangled and (not qc.is_reserved or qc.reservation == idx):
                self.net.requests[idx].canmove = True
                qc.is_reserved = True
                qc.reservation = idx
                pass
            else:
                break

    def releaselinks(self, route_nodes: List[QNode]):
        for i in range(len(route_nodes)-1):
            qc = self.get_qc(src=route_nodes[i], dest=route_nodes[i+1])
            qc.is_reserved = False
            qc.reservation = -1

    def nopp_swapping(self, src: QNode, dest: QNode, idx: int):
        #すべてのリンクでもつれ生成できていたら１回だけswapping
        tc = self._simulator.tc
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        pos = self.net.requests[idx].pos
        tmpsrc = route_nodes[pos]
        assert tmpsrc==self.own
        next_hop = route_nodes[pos+1]
        qc = self.get_qc(tmpsrc, next_hop)
        #log.debug(f"[nopp_swapping]{idx}, {qc}, {qc.is_entangled}, {qc.is_reserved}, {qc.reservation}")
        qc.is_entangled = False

        #寿命を古いリンクに合わせる
        t1 = qc.born.sec
        t2 = self.net.established[idx][2].sec
        t_sec = min(t1, t2)
        t = Time(sec=t_sec)

        if random.random() < self.p_swap: #swap成功
            self.net.requests[idx].pos += 1
            self.net.established[idx][1] = next_hop
            self.net.established[idx][2] = t
            if not next_hop == dest:
                #continue swapping
                log.debug(f"[nopp_swapping] {self.own} req {idx} {self.net.requests[idx]} success swapping {self.own} <-> {next_hop}")
            else:
                #complete the request and release links
                self.releaselinks(route_nodes=route_nodes)
                self.net.requests[idx].succeed = True
                self.net.requests[idx].waitingtime = tc.sec
                log.debug(f"[nopp_swapping]{self.own} req {idx} {self.net.requests[idx]} completed! {self.net.established[idx]}")
        else: #swap失敗
            log.debug(f"[nopp_swapping] req {idx} {self.net.requests[idx]} failed to swap {route_nodes[pos]} <-> {route_nodes[pos+1]}")
            self.est_init(idx)
            self.releaselinks(route_nodes=route_nodes)

    def opp_swapping(self, src: QNode, dest: QNode, idx: int): 
        #進めるところまでswapping　変更-> 　１回だけswapping
        tc = self._simulator.tc
        route_nodes = self.get_route_nodes(src=src, dest=dest)
        pos = self.net.requests[idx].pos
        tmpsrc = route_nodes[pos]
        assert tmpsrc==self.own
        next_hop = route_nodes[pos+1]
        qc = self.get_qc(tmpsrc, next_hop)
        log.debug(f"[opp_swapping]{idx}, {qc}, {qc.is_entangled}, {qc.is_reserved}, {qc.reservation}")
        qc.is_entangled = False

        #寿命を古いリンクに合わせる
        # t1 = qc.born.sec
        # t2 = self.net.established[idx][2].sec
        # t_sec = min(t1, t2)
        # t = Time(sec=t_sec)

        t = tc.sec

        if random.random() < self.p_swap: #swap成功
            log.debug(f"[opp_swapping]{self.own} req {idx} {self.net.requests[idx]} swapping success {self.own} <-> {next_hop}")
            self.net.requests[idx].pos += 1
            self.net.established[idx][1] = next_hop
            self.net.established[idx][2] = t
            qc.is_reserved = False
            qc.reservation = True
            if not next_hop == dest:
                #continue swapping
                log.debug(f"[opp_swapping]{self.own} req {idx} {self.net.requests[idx]} new! established link {self.net.established[idx]}")
            else:
                #complete the request
                self.net.requests[idx].succeed = True
                self.net.requests[idx].waitingtime = tc.sec
                log.debug(f"[opp_swapping]{self.own} req {idx} {self.net.requests[idx]} completed! {self.net.established[idx]}")
        else: #swap失敗
            log.debug(f"[opp_swapping] req {idx} failed to swap {route_nodes[0]} <-> {route_nodes[1]}")
            self.est_init(idx)


    def all_swapping(self, src: QNode, dest: QNode, idx: int):
        for req in self.net.requests:
            pass

        


    def eg_routine(self):
        #every time slotにおいて隣接するノード間でもつれ生成チャレンジを行う　生成できたらストップ
        tc = self._simulator.tc
        t = tc + Time(sec=1 / self.gen_rate)
        event = func_to_event(t, self.eg_routine, by=self)
        self._simulator.add_event(event) #次のtime slotにイベント追加

        #self.get_adjacent()

        #lifetimeを超えたもつれを破棄 established linkを含む
        for qc in self.adj_qc:
            if qc.is_entangled and tc.sec - qc.born.sec > self.lifetime - self.alpha:
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
                src = self.net.requests[i].src
                dest = self.net.requests[i].dest
                isallfinished = False
                node2 = self.net.established[i][1]
                if node2 == self.own: #自分がリンクの最先端ならswapチャレンジ
                    if self.isopp:
                        self.reserve_opp(src=src, dest=dest, idx=i)
                        if self.net.requests[i].canmove:
                            self.opp_swapping(src=src, dest=dest, idx=i)
                    else:
                        self.reserve_nopp(src=src, dest=dest, idx=i)
                        if self.net.requests[i].canmove:
                            self.nopp_swapping(src=src, dest=dest, idx=i)
                        
        if isallfinished:
            self.net.runtime = tc.sec
            log.debug(f"all requests finished!!")
            self._simulator.event_pool.event_list.clear()

