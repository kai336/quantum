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

FIDELITY = 0.8
MEMORY_CAPACITY = 5
MEMORY_TIME = 0.1

DROP_RATE = 0.0 #p_genでもつれ生成の確率を管理しているので０でok

LIFETIME = 30

GEN_RATE = 1 # １秒あたりのもつれ生成チャレンジ回数

P_GEN = 0.1 # もつれ生成成功確率
P_SWAP = 0.8 # swapping成功確率

NODES_NUMBER = 16
QCHANNEL_DELAY = 0.0
CCHANNEL_DELAY = 0.0

REQUESTS_NUMBER = 5

M = 5 # size of grid
N = 20 # number of request
L = 6 # lifetime(timeslot)


class AllSwappingApp(Application):
    def __init__(self, p_gen: float = P_GEN, p_swap: float = P_SWAP, gen_rate: int = GEN_RATE, lifetime: float = LIFETIME, opp_level: int = 0) -> None:
        super().__init__()
        self.p_gen = p_gen
        self.p_swap = p_swap
        self.gen_rate = gen_rate
        self.lifetime = lifetime
        self.opp_level = opp_level # 0->NOPP, 1->OPP, 2->All Swap
        self.own: QNode
        self.net: QuantumNetwork
        self.simulator: Simulator
        self.adj_qc = [] # the list of QChannel
        self.can_swap: bool = True

    def install(self, node: QNode, simulator: Simulator) -> None:
        super().install(node, simulator)
        self.own: QNode = self._node # defined in super().install
        self.net = self.own.network

        self.get_adjacent_qchannels()
        
        # initialize the QuantumNetwork
        try:
            self.net.initialized
            pass
        except AttributeError:
            self.net.initialized = True
            self.init_net()

    def reserve_nopp(self, req_idx: int) -> None:
        is_all_ready = True
        for path in self.net.requests[req_idx].paths:
            for i in range(len(path)-1):
                qc = self.get_qc(path[i], path[i+1])
                if not qc.is_entangled or (qc.reservation != req_idx):
                    is_all_ready = False
                    break
            # reserve links
            if is_all_ready:
                self.net.requests[req_idx].canmove = True
                for i in range(len(path)-1):
                    qc = self.get_qc(path[i], path[i+1])
                    qc.reservation = req_idx
                    self.net.requests[req_idx].progress.add(qc)

    def reserve_opp(self, req_idx: int) -> None:
        for path in self.net.requests[req_idx].paths:
            for i in range(len(path)-1):
                qc = self.get_qc(path[i], path[i+1])
                if qc.is_entangled and qc.reservation == -1:
                    # reserve link
                    qc.reservation = req_idx
                    self.net.requests[req_idx].progress.add(qc)
                elif qc.reservation == req_idx:
                    # already reserved
                    pass
                else:
                    # link is not available
                    break
    
    def reserve_allswap(self, req_idx: int) -> None:
        # if adjcent link exists, then reserve
        for path in self.net.requests[req_idx].paths:
            swappables = []
            for i in range(len(path)-1):
                qc = self.get_qc(path[i], path[i+1])
                if qc.is_entangled and qc.reservation == -1 and (path[i].can_swap and path[i+1].can_swap):
                    swappables.append(qc)
            for i in range(len(swappables)-1):
                if self.is_adjcent_links(swappables[i], swappables[i+1]):
                    # reserve links
                    swappables[i].reservation = req_idx
                    swappables[i+1].reservation = req_idx
                    self.net.requests[req_idx].progress.add(swappables[i])
                    self.net.requests[req_idx].progress.add(swappables[i+1])

    def is_adjcent_links(self, qc1: QuantumChannel, qc2: QuantumChannel) -> bool:
        nodes1 = qc1.node_list.copy()
        nodes1 = set(nodes1)
        nodes2 = qc2.node_list.copy()
        nodes2 = set(nodes2)
        if not nodes1.isdisjoint(nodes2) and nodes1 != nodes2:
            return True
        else:
            return False

                

                
                
    
    def releaselinks(self, path: List[QNode]):
        for i in range(len(path)-1):
            qc = self.get_qc(path[i], path[i+1])
            qc.reservation = -1
    
    def swapping_nopp(self, req_idx: int):
        tc = self._simulator.tc
        path = self.net.requests[req_idx].paths[0] # change here for multiple path algorithm

            
    def get_adjacent_qchannels(self) -> None:
        adj_qc = []
        for qc in self.net.qchannels:
            for node in qc.node_list:
                if(node == self.own):
                    adj_qc.append(qc)
        self.adj_qc = adj_qc

    def add_qchannel(self, node_list: List[QNode]) -> None:
        name = 1 + len(self.net.qchannels) # for visibility
        name = str(name) # use uuid when do expreriment
        qc = QuantumChannel(name=name, node_list=node_list)
        self.net.qchannels.append(qc)

    def remove_qchannel(self, qc:QuantumChannel) -> None:
        if qc in self.net.qchannels:
            self.net.qchannels.remove(qc)
        else:
            # write log message for debug
            pass

    def get_qc(self, src: QNode, dest: QNode) -> QuantumChannel:
        src_apps = src.get_apps(AllSwappingApp)
        for qc in src_apps[0].adj_qc:
            if dest in qc.node_list:
                return qc
        raise Exception("No qc found")

    def init_net(self) -> None:
        self.init_qc()
        self.init_progress_all()
        self.init_req_status()
        self.get_paths()

    def init_qc(self) -> None:
        for qc in self.net.qchannels:
            qc.is_entangled = False
            qc.born = self.simulator.ts

    def init_progress_all(self) -> None:
        for i, _ in enumerate(self.net.requests):
            self.init_progress_single(i)
    
    def init_progress_single(self, req_idx) -> None:
        self.net.requests[req_idx].progress = []

    def init_req_status(self) -> None:
            for req in self.net.requests:
                req.succeed = False
                req.canmove = False
                req.pos = 0 # only used in opp
                req.progress = set()

    def get_paths(self) -> None:
        # set path
        for req in self.net.requests:
            req.paths = self.get_path_single(src=req.src, dest=req.dest) # change here to implement multipath algorithm         

    def get_path_single(self, src: QNode, dest: QNode) -> List[QNode]:
        route_result = self.net.route.query(src=src, dest=dest)
        try:
            return route_result[0][2]
        except IndexError:
            log.debug(f"[get_route_nodes] {self.own} no route found: src={src}, dest={dest}")
            raise Exception("No route found")

    
    
    
    
    
