# controller_app.py
from types import SimpleNamespace
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

# 初期値
p_swap = 0.4
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数


class ControllerApp(Application):
    def __init__(self, p_swap: float = p_swap, gen_rate: int = gen_rate):
        super().__init__()
        self.p_swap = p_swap
        self.gen_rate = p_swap

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.node = node
        self._simulator = simulator
        self.net = self.node.network
        self.reuests = self.net.requests

    def init_event(self, t: Time):
        # 初期イベントを挿入
        pass

    def request_handler(self):
        # リクエストを管理
        pass

    def link_manager(self):
        # linkを管理
        # qcのリストから各qcに存在するlinkを管理

        pass
