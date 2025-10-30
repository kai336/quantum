# node_app.py
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

from research.edp.sim.link import LinkEP

# 初期値
p_swap = 0.4
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数
n_slot_per_sec = 100  # 1秒当たりのタイムスロット数


class EDPlikeNodeApp(Application):
    def __init__(
        self,
        p_swap: float = p_swap,
        gen_rate: int = gen_rate,
    ):
        super().__init__()
        self.p_swap = p_swap
        self.gen_rate = gen_rate

        self.node = None
        self._simulator = None
        self.memory = None
        self.net = None
        self.requests = None
        self.qc = None
        self.adj = []

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.node = node
        self._simulator = simulator
        self.memory = node.memories
        self.net = node.network
        self.requests = node.requests
        self.qc = node.qchannels  # 接続されてる量子チャネル

        # 隣接ノードを記録する
        for qc in self.qc:
            for node in qc.node_list:
                if node is not self.node:
                    self.adj.append(node)

        ts = simulator.ts
        self.init_event(ts)

    def init_event(self, t: Time):
        # 初期イベントを挿入
        pass

    def gen_EP(self):
        # やっぱりcontrollerでやる
        pass

    def op_handler(self):
        # controllerからの命令ハンドラ
        pass

    def swap(self, qc1: QuantumChannel, qc2: QuantumChannel):
        # swap操作
        pass

    def purify(self, qc1: QuantumChannel, qc2: QuantumChannel):
        # purify操作
        pass
