# controller_app.py
# main duty: controll the entire network
import random
from typing import Dict, List, Optional, Tuple

import qns.utils.log as log
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
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

# 初期値
p_swap = 0.4
p_pur = 0.9
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数
f_req = 0.97  # 最小要求忠実度
f_cut = 0.70  # 切り捨て閾値
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
        f_cut=f_cut,
    ):
        super().__init__()
        self.p_swap: float = p_swap
        self.p_pur: float = p_pur
        self.gen_rate: int = gen_rate
        self.f_req: float = f_req
        self.f_cut: float = f_cut
        self.net: QuantumNetwork
        self.node: QNode
        self.requests: List[NewRequest] = []
        self.links: List[LinkEP] = []  # シンプルにlinkEPぶち込んでEP管理
        self.links_next: List[LinkEP] = []  # 次のタイムスロットで使えるようになる新EP
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
        # gen_ep -> req_routine -> link_manager_routine -> gen_ep -> ...
        gen_ep_routine = func_to_event(t=t, fn=self.gen_EP_routine, by=self)
        self._simulator.add_event(gen_ep_routine)
        # req_routine = func_to_event(t=t, fn=self.request_handler_routine, by=self)
        # self._simulator.add_event(req_routine)
        # link_routine = func_to_event(t=t, fn=self.links_manager_routine, by=self)
        # self._simulator.add_event(link_routine)

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
            fidelity_init: float = 0.99  # change here to set random fidelity
            name = qc.name
            node_list = qc.node_list
            new_qc = NewQC(
                name=name,
                node_list=node_list,
                fidelity_init=fidelity_init,
                memory_capacity=l0_link_max,
            )
            new_qcs.append(new_qc)

        self.new_qcs = new_qcs

    def gen_EP_routine(self):
        # 全チャネルでリンクレベルもつれ生成
        print(self._simulator.tc, "gen ep routine start")
        tc = self._simulator.tc
        for qc in self.new_qcs:
            if not qc.has_free_memory:
                continue

            nodes = qc.node_list
            _ = self.gen_single_EP(
                src=nodes[0],
                dest=nodes[1],
                fidelity=qc.fidelity_init,
                t=tc,
                qc=qc,
            )
            # print(self._simulator.tc, "gen link")

        self._add_tick_event(fn=self.request_handler_routine)

    def request_handler_routine(self):
        # リクエストを管理
        # req.swap_plan, req.swap_progressから各操作を実行\
        print(self._simulator.tc, "req routine start")
        is_all_done = True
        for req in self.requests:
            # 終了判定
            root_op, ops = req.swap_plan
            assert isinstance(root_op, Operation)
            idx = self.requests.index(req)
            if req.is_done:
                # print("!!!!!!!!req", idx, " finished!!!!!!!!")
                continue
            elif root_op.status == OpStatus.DONE and root_op.ep.fidelity >= self.f_req:
                # f_reqも終了条件に加える
                req.is_done = True
                print(
                    "!!!!!!!!req", idx, " finished!!!!!!!! fid: ", root_op.ep.fidelity
                )
                continue
            else:
                is_all_done = False
                self._advance_request(req, root_op, ops)

        if is_all_done:
            # 全リクエスト終わったらシミュレータのイベント全消しして終了
            # TODO self.result = [time, ...]
            log.debug("!!!!!!!!all requests finished!!!!!!!!!")
            self._simulator.event_pool.event_list.clear()
            return

        self._add_tick_event(fn=self.links_manager_routine)

    def links_manager_routine(self):
        # self.linksからLinkEPのデコヒーレンスを管理
        # self.links_next　を次のタイムスロットでself.linksに挿入
        print(self._simulator.tc, "link routine start")

        if len(self.links_next) != 0:
            self.links += self.links_next

        # print("links: ", [link.fidelity for link in self.links])
        dt = Time(time_slot=3).sec  # 3 timeslotをsec単位に変換
        for link in list(self.links):  # 途中でリンクが削除されても安全に回す
            link.decoherence(dt=dt)
            if link.fidelity < f_cut:  # f_cut以下のもつれを切り捨てる
                self.decoherence_EP(link)
        self.links_next.clear()

        self._add_tick_event(fn=self.gen_EP_routine)

    def _advance_request(
        self, req: NewRequest, root_op: Operation, ops: List[Operation]
    ):
        # リクエストを１操作分進める
        # 現時点でREADYなopだけ実行
        ready_ops = [op for op in ops if op.status == OpStatus.READY]
        for op in ready_ops:  # コピー使うことで1操作分以上進まないようにする
            print(self._simulator.tc, op, "start op")
            self._run_op(req, op)

    def _run_op(self, req: NewRequest, op: Operation):
        # 操作を実行
        op.start()
        if op.type == OpType.GEN_LINK:
            self._handle_gen_link(op)
        elif op.type == OpType.SWAP:
            self._handle_swap(op)
        elif op.type == OpType.PURIFY:
            self._handle_purify(op)

    def _handle_gen_link(self, op: Operation):
        # 生成済みEPを探す
        pair = set((op.n1, op.n2))
        ep_cand: Optional[LinkEP] = None
        for link in self.links:
            if set(link.nodes) == pair and link.is_free:
                ep_cand = link
                break
        if ep_cand is None:
            # まだEPなし
            print(self._simulator.tc, "no link")
            op.request_regen()  # 再試行できるようREADYに戻す
            return

        print(self._simulator.tc, "gen link success")
        ep_cand.set_owner(op)
        op.done()

    def _handle_swap(self, op: Operation):
        # swap
        ep_left = op.children[0].ep
        ep_right = op.children[1].ep
        assert ep_left is not None and ep_right is not None
        assert ep_left in self.links and ep_right in self.links

        # 一応中間ノードの整合性チェック
        via = op.via
        assert via is not None
        assert via in ep_left.nodes and via in ep_right.nodes

        # 先にもとのもつれを廃棄しとく
        # 失敗・成功にかかわらずもとのもつれは使えない　& 新たにメモリ消費することなくswapできるので
        self.consume_EP(ep_left)
        self.consume_EP(ep_right)

        # swap
        if random.random() < self.p_swap:
            # 新しいEP生成
            new_fid = f_swap(ep_left.fidelity, ep_right.fidelity)
            tc = self._simulator.tc
            new_ep = self.gen_single_EP(op.n1, op.n2, fidelity=new_fid, t=tc)
            new_ep.set_owner(op)
            op.done()
            print(self._simulator.tc, "swap success")
        else:
            # 再生成要求
            print(self._simulator.tc, "swap failed")
            op.request_regen()

    def _handle_purify(self, op: Operation):
        # purify
        # fidを更新
        # purify 準備
        assert len(op.pur_eps) == 2
        ep_sacrifice, ep_target = op.pur_eps
        assert ep_target is not None and ep_sacrifice is not None

        fid_target = ep_target.fidelity
        fid_sacrifice = ep_sacrifice.fidelity

        self.consume_EP(ep_sacrifice)  # どっちにしろ犠牲になるのでfidも取ったし消しとく
        new_fid = f_pur(ft=fid_target, fs=fid_sacrifice)  # purify成功後のfidelity

        op.pur_eps.clear()
        # purify　実行
        if random.random() < self.p_pur:
            print(self._simulator.tc, "purify success")
            ep_target.fidelity = new_fid  # fidelity更新
            # すでにownerは自分になっているので念のため確認だけする
            if ep_target.owner_op is not op:
                pre = op.children[0]
                ep_target.change_owner(pre_owner=pre, new_owner=op)
            op.done()
        else:  # 失敗したらtargetEPも消す
            print(self._simulator.tc, "purify failed")
            self.consume_EP(ep_target)
            op.request_regen()

        assert len(op.pur_eps) == 0

    def gen_single_EP(
        self,
        src: QNode,
        dest: QNode,
        fidelity: float,
        t: Time,
        qc: NewQC | None = None,
        is_free: bool = True,
    ) -> LinkEP | None:
        # リンク(NewQC)単位のメモリ制約で管理する
        if qc is not None and not qc.has_free_memory:
            return None

        if qc is not None:
            qc.use_single_memory()

        link = LinkEP(
            fidelity=fidelity,
            nodes=(src, dest),
            qc=qc,
            created_at=t,
            is_free=is_free,
        )
        self.links.append(link)
        return link

    def decoherence_EP(self, ep: LinkEP):
        # デコヒーレンスによってLinkEPが切り捨てられるとき
        owner = ep.owner_op
        if owner:
            owner.request_regen()
            ep.free_owner(owner)
        self.delete_EP(ep)

    def consume_EP(self, ep: LinkEP):
        # opの実行によってLinkEPが消費されるとき
        # opの所有epから消す
        assert ep.owner_op is not None
        ep.free_owner(pre_owner=ep.owner_op)
        self.delete_EP(ep=ep)

    def delete_EP(self, ep: LinkEP):
        # LinkEPをself.linksから削除、インスタンスも削除
        if ep.qc is not None:
            ep.qc.free_single_memory()
        self.links.remove(ep)
        del ep

    def _add_tick_event(self, fn):
        t_tick = Time(time_slot=1)
        tc = self._simulator.tc
        tn = tc.__add__(t_tick)
        next_event = func_to_event(t=tn, fn=fn, by=self)
        self._simulator.add_event(next_event)
