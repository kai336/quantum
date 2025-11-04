# controller_app.py
from types import SimpleNamespace
from typing import Dict, Optional, List
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork, Request
from qns.simulator.ts import Time

import qns.utils.log as log
import random

from research.edp.sim.new_request import NewRequest
from research.edp.sim.link import LinkEP

# 初期値
p_swap = 0.4
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数
f_req = 0.8  # 最小要求忠実度
init_fidelity = 0.99


class ControllerApp(Application):
    def __init__(self, p_swap: float = p_swap, gen_rate: int = gen_rate, f_req=f_req):
        super().__init__()
        self.p_swap: float = p_swap
        self.gen_rate: int = gen_rate
        self.f_req: float = f_req
        self.net: QuantumNetwork = None
        self.node: QNode = None
        self.requests: List[NewRequest] = []
        self.links: List[tuple(QNode, QNode, List[LinkEP])] = []  # src, dest, links
        self.requests = []
        self.nodes = []

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.node = node
        self.net = node.network

        # self.nodesでネットワーク上のノードを管理
        self.nodes: List[QNode] = node.network.nodes
        for n in self.nodes:
            if n is self.node:
                self.nodes.remove(n)  # 自分自身(controller)をのぞく
                break

    def init_reqs(self):
        # self.requestsでリクエストを管理
        # QNSのRequest -> オリジナルのNewRequestクラスに変換
        for i in range(len(self.net.requests)):
            req = self.net.requests[i]
            src = req.src
            dest = req.dest
            name = f"req{i}"
            swap_plan = EDP(src, dest, f_req)  # ここで経路計算
            new_req = NewRequest(
                src=src, dest=dest, name=name, priority=0, swap_plan=swap_plan
            )  # リクエストのインスタンス作成
            self.requests.append(new_req)

    def init_links(self):
        # linkを管理するself.links
        # EPを簡易的にlinkとして取り扱う
        for i in range(len(self.net.qchannels)):
            qc = self.net.qchannels[i]
            link = tuple(qc.src, qc.dest, [])
            self.links.append(link)

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

    def gen_EP(self, src: QNode, dest: QNode):
        # 1つのLinkEPを確定的に生成する
        tc = self._simulator.tc()
        link = LinkEP(fidelity=init_fidelity, nodes=(src, dest), created_at=tc)
        self.links.append(link)
