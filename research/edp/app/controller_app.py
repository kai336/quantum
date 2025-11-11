# controller_app.py
# main duty: controll the entire network
from typing import Dict, Optional, List, Tuple
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

from research.edp.sim.new_request import NewRequest
from research.edp.sim.link import LinkEP
from research.edp.alg.edp import batch_EDP
from research.edp.sim.new_qchannel import NewQC

# 初期値
p_swap = 0.4
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数
f_req = 0.8  # 最小要求忠実度
init_fidelity = 0.99
l0_link_max = 5  # リンクレベルEPのバッファ数


class ControllerApp(Application):
    """
    ネットワーク全体を制御(EP生成、スワップ計画、リクエスト管理)
    """

    def __init__(self, p_swap: float = p_swap, gen_rate: int = gen_rate, f_req=f_req):
        super().__init__()
        self.p_swap: float = p_swap
        self.gen_rate: int = gen_rate
        self.f_req: float = f_req
        self.net: QuantumNetwork
        self.node: QNode
        self.requests: List[NewRequest] = []
        self.links: List[LinkEP] = []  # シンプルにlinkEPぶち込んでEP管理
        # self.fidelity: List[float] = []  # i番目のqcで生成されるlinkのフィデリティ初期値
        self.nodes: List[QNode] = []
        self.new_net: QuantumNetwork = None  # ここに初期fidelityを記録

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.node = node
        self.net = node.network
        self.new_net = node.network

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
            # swap_plan = EDP(src, dest, f_req)  # ここで経路計算
            new_req = NewRequest(
                src=src, dest=dest, name=name, priority=0
            )  # リクエストのインスタンス作成
            self.requests.append(new_req)

        self.route_EDP()  # ルーティングテーブル作成

    def route_EDP(self):
        # EDPのルーティングテーブル作成
        swap_plans = batch_EDP(qnet=self.new_net)
        for i in len(swap_plans):
            self.requests[i].swap_plans = swap_plans[i]

    # iranai
    def init_links(self):
        # linkを管理するself.links
        # EPを簡易的にlinkとして取り扱う
        # memory capacityをどう扱うか？->各ノードへの問い合わせ、占有数だけを考える&self.linksでは気にしない
        # 初期状態はリンクレベルだけ
        for i in range(len(self.net.qchannels)):
            qc = self.net.qchannels[i]
            link = Tuple(qc.src, qc.dest, [])
            self.links.append(link)

    def init_qcs(self):
        # qc.fidelityを設定
        new_qcs: NewQC = []
        for qc in self.net.qchannels:
            fidelity_init = 0.99  # change here to set random fidelity
            name = qc.name
            node_list = qc.node_list
            new_qc = NewQC(name=name, node_list=node_list, fidelity_init=fidelity_init)
            new_qcs.append(new_qc)
        self.new_net.qchannles = None
        self.new_net.qchannles = new_qc
        self.new_qc = new_qc

    def init_event(self, t: Time):
        # 初期イベントを挿入
        pass

    def request_handler(self):
        # リクエストを管理
        pass

    def links_manager(self):
        # linkを管理
        # qcのリストから各qcに存在するlinkを管理
        pass

    def gen_single_EP(self, src: QNode, dest: QNode, fidelity: float):
        # 1つのLinkEPを確定的に生成する
        link = LinkEP(fidelity=fidelity, nodes=(src, dest), created_at=tc)
        self.links.append(link)

    def routine_gen_EP(self):
        # 全チャネルでリンクレベルもつれ生成
        # ５本のもつれあればそれ以上いらない
        for qc in self.new_qc:
            nodes = qc.node_list
            # 同じチャネルのリンクレベルEPを数える
            num_link = 0
            for link in self.links:
                if set(link.nodes) == set(nodes):
                    num_link += 1
            if num_link < l0_link_max:
                self.gen_single_EP(
                    src=nodes[0], dest=nodes[1], fidelity=qc.fidelity_init
                )

    def has_free_memory(self, node: QNode) -> bool:
        # ノードのメモリに空きがあるか
        app = node.apps[0]
        return app.memory_capacity > app.memory_usage
