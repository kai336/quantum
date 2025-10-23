# EDPlikeNodeApp.py
from typing import Dict, Optional, List
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
from qns.simulator.ts import Time
import qns.utils.log as log
import random

p_swap = 0.4
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1

drop_rate = 0.0  # p_genでもつれ生成の確率を管理しているので０でok

lifetime = 30
decoherence_rate = 1 / lifetime

gen_rate = 1  # １秒あたりのもつれ生成回数

# network settings
nodes_number = 7
qchannel_delay = 0.0
cchannel_delay = 0.0
M = 5
N = 20
L = 6
request_number = 5


class EDPlikeNodeApp(Application):
    def __init__(
        self,
        p_swap: float = p_swap,
        gen_rate: int = gen_rate,
    ):
        super().__init__()
        self.p_swap = p_swap
        self.gen_rate = gen_rate

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.node = node
        self._simulator = simulator
        self.memory = self.node.memories
        self.net = self.node.network
        self.requests = self.node.requests
        