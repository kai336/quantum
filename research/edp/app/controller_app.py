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

from edp.sim.new_request import NewRequest
from edp.sim.link import LinkEP
from edp.alg.edp import batch_EDP
from edp.sim.new_qchannel import NewQC

"""
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!TODO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
swap_plan, swap_progressをどうするか真面目に考える
深さごとに配列にする？
swap_plan[0]=[op, op, ...] -> リンクレベル(深さ0)の操作の配列
・・・
swap_plan[i]=[op, op, ...] -> 深さi
op.op
op.parent
op.child
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!TODO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

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
        self.nodes: List[QNode] = node.network.nodes.copy()
        for n in self.nodes:
            if n is self.node:
                self.nodes.remove(n)  # 自分自身(controller)をのぞく
                break

        self.init_qcs()
        self.init_reqs()

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

        self.net.requests = self.requests.copy()
        self.route_EDP()  # ルーティングテーブル作成

    def route_EDP(self):
        # EDPのswaping tree作成
        swap_plans = batch_EDP(qnet=self.new_net, gen_rate=self.gen_rate)
        for i in range(len(swap_plans)):
            self.requests[i].swap_plan = swap_plans[i]

    # iranai
    """
    def init_links(self):
        # linkを管理するself.links
        # EPを簡易的にlinkとして取り扱う
        # memory capacityをどう扱うか？->各ノードへの問い合わせ、占有数だけを考える&self.linksでは気にしない
        # 初期状態はリンクレベルだけ
        for i in range(len(self.net.qchannels)):
            qc = self.net.qchannels[i]
            link = (qc.node_list[0], qc.node_list[1], [])
            self.links.append(link)
    """

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
        self.new_net.qchannles = new_qcs
        self.net.new_qcs = new_qcs
        self.new_qc = new_qcs

    def init_event(self, t: Time):
        # 初期イベントを挿入
        pass

    def request_handler(self):
        # リクエストを管理
        # req.swap_plan, req.swap_progressから各操作を実行
        for req in self.requests:
            req.swap_plan

    def op_handler(self, op: str, n1: QNode, n2: QNode):
        if op == "swap":
            self.swap(n1, n2)
        elif op == "purify":
            self.purify(n1, n2)

    def swap(self, n1: QNode, n2: QNode):
        # swap
        pass

    def purify(self, n1: QNode, n2: QNode):
        # purify
        pass

    def links_manager(self):
        # linkを管理
        # qcのリストから各qcに存在するlinkを管理
        pass

    def gen_single_EP(self, src: QNode, dest: QNode, fidelity: float, t: Time):
        # 1つのLinkEPを確定的に生成する
        link = LinkEP(fidelity=fidelity, nodes=(src, dest), created_at=t)
        self.links.append(link)

    def routine_gen_EP(self):
        # 全チャネルでリンクレベルもつれ生成
        # ５本のもつれあればそれ以上いらない
        tc = self._simulator.tc()
        for qc in self.new_qc:
            nodes = qc.node_list
            # 同じチャネルのリンクレベルEPを数える
            num_link = 0
            for link in self.links:
                if set(link.nodes) == set(nodes):
                    num_link += 1
            if num_link < l0_link_max:
                self.gen_single_EP(
                    src=nodes[0], dest=nodes[1], fidelity=qc.fidelity_init, t=tc
                )
        # TODO: genrateに応じて次のイベントを追加

    def has_free_memory(self, node: QNode) -> bool:
        # ノードのメモリに空きがあるか
        app = node.apps[0]
        return app.memory_capacity > app.memory_usage
