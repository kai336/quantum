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
        self.simulator: Simulator
        self.adj_qc = [] # the list of QChannel
        self.flags = {'is_entangled': False, 'is_swapped': False, 'can_swap': False}

    def install(self, node: QNode, simulator: Simulator) -> None:
        super().install(node, simulator)
        self.own: QNode = self._node # defined in super().install
        self.net = self.own.network

        ts = simulator.ts # the start time of the simulator
        
        # initialize the QuantumNetwork
        try:
            self.net.initialized
            pass
        except AttributeError:
            self.net.initialized = True


    def get_paths_all(self, src: QNode, dest: QNode) -> List[QNode]:
        # get list of nodes in single path
        # change here to implement multipath algorithm
        for req in self.net.requests:
            route_result = self.net.route.query(src=req.src, dest=req.dest)
        try:
            return route_result[0][2]
        except IndexError:
            log.debug(f"[get_route_nodes] {self.own} no route found: src={src}, dest={dest}")
            raise Exception("No route found")
        