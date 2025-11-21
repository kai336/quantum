# controller_app.py
# main duty: controll the entire network
import copy
import random
from os.path import isfile
from typing import Dict, List, Optional, Tuple

import qns.utils.log as log
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.network import QuantumNetwork
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.simulator.ts import Time

from edp.alg.edp import batch_EDP
from edp.app.node_app import NodeApp
from edp.sim.link import LinkEP
from edp.sim.models import f_pur, f_swap
from edp.sim.new_qchannel import NewQC
from edp.sim.new_request import NewRequest
from edp.sim.op import Operation, OpStatus, OpType

"""
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!TODO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
swap_plan, swap_progressをどうするか真面目に考える
opクラスつくって、各操作ごとに完了したかどうかを考える
swap_plan = [op1, op2, ...]
op.op
op.parent
op.child
op.status
op.ep <- この操作が完了した後にできるもつれ
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!TODO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

# 初期値
p_swap = 0.4
p_pur = 0.9
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数
f_req = 0.97  # 最小要求忠実度
init_fidelity = 0.99
l0_link_max = 5  # リンクレベルEPのバッファ数


class ControllerApp(Application):
    """
    ネットワーク全体を制御(EP生成、スワップ計画、リクエスト管理)
    """

    def __init__(
        self,
        p_swap: float = p_swap,
        p_pur: float = p_pur,
        gen_rate: int = gen_rate,
        f_req=f_req,
    ):
        super().__init__()
        self.p_swap: float = p_swap
        self.p_pur: float = p_pur
        self.gen_rate: int = gen_rate
        self.f_req: float = f_req
        self.net: QuantumNetwork
        self.node: QNode
        self.requests: List[NewRequest] = []
        self.links: List[LinkEP] = []  # シンプルにlinkEPぶち込んでEP管理
        # self.fidelity: List[float] = []  # i番目のqcで生成されるlinkのフィデリティ初期値
        self.nodes: List[QNode] | None = None

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.node = node
        assert isinstance(node.network, QuantumNetwork)
        self.net = node.network

        # self.nodesでネットワーク上のノードを管理
        self.nodes = node.network.nodes.copy()
        for n in self.nodes:
            if n is self.node:
                self.nodes.remove(n)  # 自分自身(controller)をのぞく
                break

        # 各種初期設定
        self.init_qcs()
        self.init_reqs()
        ts = self._simulator.ts
        self.init_event(t=ts)

    def init_event(self, t: Time):
        # 初期イベントを挿入
        ep_routine = func_to_event(t=t, fn=self.routine_gen_EP, by=self)
        self._simulator.add_event(ep_routine)
        req_routine = func_to_event(t=t, fn=self.request_handler_routine, by=self)
        self._simulator.add_event(req_routine)

    def init_reqs(self):
        # self.requestsでリクエストを管理
        # QNSのRequest -> オリジナルのNewRequestクラスに変換
        for i in range(len(self.net.requests)):
            req = self.net.requests[i]
            src = req.src
            dest = req.dest
            name = f"req{i}"
            new_req = NewRequest(
                src=src, dest=dest, name=name, priority=0, f_req=f_req
            )  # リクエストのインスタンス作成
            self.requests.append(new_req)

        self.build_EDP()  # ルーティングテーブル作成

    def build_EDP(self):
        # EDPのswaping tree作成
        swap_plans = batch_EDP(
            qnet=self.net, reqs=self.requests, qcs=self.new_qcs, gen_rate=self.gen_rate
        )
        for i in range(len(swap_plans)):
            self.requests[i].swap_plan = swap_plans[i]

    def init_qcs(self):
        # qc.fidelityを設定
        new_qcs: List[NewQC] = []
        for qc in self.net.qchannels:
            fidelity_init = 0.99  # change here to set random fidelity
            name = qc.name
            node_list = qc.node_list
            new_qc = NewQC(name=name, node_list=node_list, fidelity_init=fidelity_init)
            new_qcs.append(new_qc)

        self.new_qcs = new_qcs

    def request_handler_routine(self):
        # リクエストを管理
        # req.swap_plan, req.swap_progressから各操作を実行
        # !!!!!TODO!!!!!: 終了判定
        for req in self.requests:
            root_op, ops = req.swap_plan
            self._advance_request(req, root_op, ops)

    def _advance_request(
        self, req: NewRequest, root_op: Operation, ops: List[Operation]
    ):
        # リクエストを１操作分進める
        for op in ops:
            # op.judge_ready() # OPに更新あったとき、連鎖的に接続されるOPも更新されるのでいらない説
            if op.status == OpStatus.READY:
                self._run_op(req, op)

    def _run_op(self, req: NewRequest, op: Operation):
        # 操作を実行
        op.start()
        if op.op == OpType.GEN_LINK:
            self._handle_gen_link(op)
        elif op.op == OpType.SWAP:
            self._handle_swap(op)
        elif op.op == OpType.PURIFY:
            self._handle_purify(op)

    def _handle_gen_link(self, op: Operation):
        # 生成済みEPを探す
        pair = set((op.n1, op.n2))
        cand: Optional[LinkEP] = None
        for link in self.links:
            if set(link.nodes) == pair and link.is_free:
                cand = link
                break
        if cand is None:
            # まだEPなし
            op.status = OpStatus.WAITING
            return

        op.ep = cand  # OPにEPを紐づけ
        cand.is_free = False  # EPの状態更新
        op.finish()

    def _handle_swap(self, op: Operation):
        # swap
        ep_left = op.children[0].ep
        ep_right = op.children[1].ep
        assert ep_left is not None and ep_right is not None

        # 一応中間ノードの整合性チェック
        via = op.via
        assert via in ep_left.nodes and via in ep_right.nodes

        # 先にもとのもつれを廃棄しとく
        # 失敗・成功にかかわらずもとのもつれは使えない　& 新たにメモリ消費することなくswapできるので
        self.delete_EP(ep_left)
        self.delete_EP(ep_right)

        # swap
        if random.random() < self.p_swap:
            # 新しいEP生成
            new_fid = f_swap(ep_left.fidelity, ep_right.fidelity)
            tc = self._simulator.tc
            op.ep = self.gen_single_EP(op.n1, op.n2, fidelity=new_fid, t=tc)
            op.finish()
        else:
            op.failed()

    def _handle_purify(self, op: Operation):
        # purify
        # fidを更新
        # ほんとに正しい実装か？
        # op.childrenが２つあれば準備完了
        # purify 準備
        ep_left = op.children[0].ep
        ep_right = op.children[1].ep
        assert ep_left is not None and ep_right is not None

        fid_l = ep_left.fidelity
        fid_r = ep_right.fidelity
        if fid_l < fid_r:
            # rが犠牲
            self.delete_EP(ep_right)
            new_fid = f_pur(ft=fid_l, fs=fid_r)

        else:
            # lが犠牲
            self.delete_EP(ep_left)
            new_fid = f_pur(ft=fid_r, fs=fid_l)

        # purify　実行
        if random.random() < self.p_pur:
            tc = self._simulator.tc
            op.ep = self.gen_single_EP(
                src=op.n1, dest=op.n2, fidelity=new_fid, t=tc, is_free=False
            )
        else:
            if ep_left is None:
                self.delete_EP(ep_right)
            else:
                self.delete_EP(ep_left)

        op.finish()

    def links_manager(self):
        # qcのリストから各qcに存在するlinkを管理
        # デコヒーレンスを制御
        # 各ノードのmemory管理ともいえる
        pass

    def gen_single_EP(
        self, src: QNode, dest: QNode, fidelity: float, t: Time, is_free: bool = True
    ) -> LinkEP | None:
        # 1つのLinkEPをメモリに空きがあればに生成する
        if not (self.has_free_memory(src) and self.has_free_memory(dest)):
            return None
        else:
            self.use_single_memory(src)
            self.use_single_memory(dest)
            link = LinkEP(
                fidelity=fidelity, nodes=(src, dest), created_at=t, is_free=is_free
            )
            self.links.append(link)
            return link

    def routine_gen_EP(self):
        # 全チャネルでリンクレベルもつれ生成
        # ５本のもつれあればそれ以上いらない
        # メモリに空きがあるかも判定する
        tc = self._simulator.tc
        for qc in self.new_qcs:
            nodes = qc.node_list
            # 同じチャネルのリンクレベルEPを数える
            num_link = 0
            for link in self.links:
                if set(link.nodes) == set(nodes):
                    num_link += 1
            if num_link < l0_link_max:
                _ = self.gen_single_EP(
                    src=nodes[0], dest=nodes[1], fidelity=qc.fidelity_init, t=tc
                )

        # TODO: genrateに応じて次のイベントを追加

    def has_free_memory(self, node: QNode) -> bool:
        # ノードのメモリに空きがあるか
        assert isinstance(node.apps[0], NodeApp)
        app: NodeApp = node.apps[0]
        return app.has_free_memory

    def use_single_memory(self, node: QNode):
        assert isinstance(node.apps[0], NodeApp)
        app: NodeApp = node.apps[0]
        app.use_single_memory

    def free_single_memory(self, node: QNode):
        assert isinstance(node.apps[0], NodeApp)
        app: NodeApp = node.apps[0]
        app.free_single_memory

    def delete_EP(self, ep: LinkEP):
        # メモリ開放とself.linksから削除
        for node in ep.nodes:
            self.free_single_memory(node)
        self.links.remove(ep)
        del ep
