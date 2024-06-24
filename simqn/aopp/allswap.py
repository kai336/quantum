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
        self.net.requests:
        self.simulator: Simulator
        self.adj_qc = [] # the list of QChannel
        self.can_swap: bool = False

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
    
    def init_progress_single(self, idx_req) -> None:
        self.net.requests[idx_req].progress = []

    def init_req_status(self) -> None:
            for req in self.net.requests:
                req.succeed = False
                req.canmove = False
                req.pos = 0 # only used in opp
                req.progress = []

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

    
    
    
    
    
