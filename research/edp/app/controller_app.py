# controller_app.py
# main duty: controll the entire network
import random
from typing import Dict, List, Optional

import qns.utils.log as log
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.network import QuantumNetwork
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.simulator.ts import Time

from edp.alg.edp import batch_EDP
from edp.sim.ep import EP
from edp.sim.models import f_pur, f_swap, p_pur
from edp.sim.new_qchannel import NewQC
from edp.sim.new_request import NewRequest
from edp.sim.op import Operation, OpStatus, OpType

# 初期値
p_swap = 0.4
# p_pur = 0.9
target_fidelity = 0.8
memory_capacity = 5
memory_time = 0.1
gen_rate = 50  # １秒あたりのもつれ生成回数
f_req = 0.85  # 最小要求忠実度
f_cut = 0.70  # 切り捨て閾値
init_fidelity = 0.99
l0_link_max = 5  # リンクレベルEPのバッファ数
max_pump_step = 3


class ControllerApp(Application):
    """
    ネットワーク全体を制御(EP生成、スワップ計画、リクエスト管理)
    """

    def __init__(
        self,
        p_swap: float = p_swap,
        # p_pur: float = p_pur,
        gen_rate: int = gen_rate,
        f_req=f_req,
        f_cut=f_cut,
        init_fidelity: float = init_fidelity,
        enable_pumping: bool = True,
        max_pump_step: int = max_pump_step,
    ):
        super().__init__()
        self.p_swap: float = p_swap
        # self.p_pur: float = p_pur
        self.gen_rate: int = gen_rate
        self.f_req: float = f_req
        self.f_cut: float = f_cut
        self.init_fidelity: float = init_fidelity
        self.net: QuantumNetwork
        self.node: QNode
        self.requests: List[NewRequest] = []
        self.links: List[EP] = []  # シンプルにlinkEPぶち込んでEP管理
        self.links_next: List[EP] = []  # 次のタイムスロットで使えるようになる新EP
        # self.fidelity: List[float] = []  # i番目のqcで生成されるlinkのフィデリティ初期値
        self.nodes: List[QNode] | None = None
        self.completed_requests: List[dict] = []
        self.completed_requests: List[dict] = []
        self.enable_pumping: bool = enable_pumping
        self.max_pump_step: int = max_pump_step
        self.pumping_ops: List[Operation] = []
        self.pump_op_target: Dict[Operation, Operation] = {}

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
        for i, plan in enumerate(swap_plans):
            if plan is None:
                log.logger.warning(
                    f"swap plan not found for request {self.requests[i].name}"
                )
                self.requests[i].is_done = True
                continue
            self.requests[i].swap_plan = plan
            _, ops = plan
            for op in ops:
                op.request = self.requests[i]

    def init_qcs(self):
        # qc.fidelityを設定
        new_qcs: List[NewQC] = []
        for qc in self.net.qchannels:
            fidelity_init: float = self.init_fidelity
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
            if req.swap_plan is None:
                if not req.is_done:
                    log.logger.warning(f"skip request without swap plan: {req.name}")
                    req.is_done = True
                continue

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
                finish_time = self._simulator.tc.time_slot
                self.completed_requests.append(
                    {
                        "index": idx,
                        "name": req.name,
                        "finish_time": finish_time,
                        "fidelity": root_op.ep.fidelity,
                    }
                )
                print(
                    "!!!!!!!!req", idx, " finished!!!!!!!! fid: ", root_op.ep.fidelity
                )
                continue
            else:
                is_all_done = False
                self._advance_request(req, root_op, ops)

        self._advance_pumping_ops()

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

    def _run_op(self, req: Optional[NewRequest], op: Operation):
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
        ep_cand: Optional[EP] = None
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
        if op in self.pump_op_target:
            target = self.pump_op_target.get(op)
            self._cleanup_pump_op(op)
            if target is not None:
                self._on_sacrificial_ep_ready(sacrificial_op=op, target_op=target)
        else:
            self._maybe_start_pumping(op)

    def _handle_swap(self, op: Operation):
        # swap
        ep_left = op.children[0].ep
        ep_right = op.children[1].ep
        if (
            ep_left is None
            or ep_right is None
            or ep_left not in self.links
            or ep_right not in self.links
        ):
            # 必要なEPがデコヒーレンス等で欠落したら再生成を要求する
            op.request_regen()
            return

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
            self._maybe_start_pumping(op)
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
        success = False
        # purify　実行
        if random.random() < p_pur(ft=fid_target, fs=fid_sacrifice):
            print(self._simulator.tc, "purify success")
            ep_target.fidelity = new_fid  # fidelity更新
            # すでにownerは自分になっているので念のため確認だけする
            if ep_target.owner_op is not op:
                pre = op.children[0]
                ep_target.change_owner(pre_owner=pre, new_owner=op)
            op.done()
            success = True
        else:  # 失敗したらtargetEPも消す
            print(self._simulator.tc, "purify failed")
            self.consume_EP(ep_target)
            op.request_regen()
            success = False

        assert len(op.pur_eps) == 0
        if op in self.pump_op_target:
            target = self.pump_op_target.pop(op)
            self._cleanup_pump_op(op)
            self._on_pump_purify_done(
                purify_op=op,
                target_op=target,
                success=success,
                target_ep=ep_target,
                new_fid=new_fid if success else None,
            )
        elif success:
            self._maybe_start_pumping(op)

    def _is_swap_waiting(self, op_child: Operation) -> bool:
        op_parent = op_child.parent
        if op_parent is None:
            return False
        if op_parent.type != OpType.SWAP:
            return False
        if len(op_parent.children) < 2:
            return False

        left = op_parent.children[0]
        right = op_parent.children[1]
        other = right if op_child is left else left
        if other.status in (OpStatus.DONE, OpStatus.READY):
            return False
        return True

    def _maybe_start_pumping(self, op_child: Operation):
        if not self.enable_pumping:
            return
        if op_child.ep is None:
            return
        if not self._is_swap_waiting(op_child):
            return
        req = getattr(op_child, "request", None)
        if req is not None and hasattr(req, "use_pumping") and not req.use_pumping:
            return

        op_child.is_pump_target = True
        op_child.parent_swap = op_child.parent
        if not self._has_pending_pump(op_child):
            self._schedule_pump_gen_link(target_op=op_child)

    def _has_pending_pump(self, target_op: Operation) -> bool:
        return any(t is target_op for t in self.pump_op_target.values())

    def _should_stop_pumping(self, target_op: Operation) -> bool:
        if not self.enable_pumping:
            return True
        req = getattr(target_op, "request", None)
        if req is not None and hasattr(req, "use_pumping") and not req.use_pumping:
            return True
        if target_op.ep is None:
            return True
        if not self._is_swap_waiting(target_op):
            return True
        if target_op.pump_step >= self.max_pump_step:
            return True
        return False

    def _schedule_pump_gen_link(self, target_op: Operation):
        if self._should_stop_pumping(target_op):
            self._clear_pump_state(target_op)
            return

        name = f"PUMP_GEN_LINK({target_op.n1.name}-{target_op.n2.name})-step{target_op.pump_step + 1}"
        op = Operation(
            name=name,
            type=OpType.GEN_LINK,
            n1=target_op.n1,
            n2=target_op.n2,
            status=OpStatus.READY,
            request=target_op.request,
            parent_swap=target_op.parent_swap,
        )
        self.pumping_ops.append(op)
        self.pump_op_target[op] = target_op

    def _on_sacrificial_ep_ready(self, sacrificial_op: Operation, target_op: Operation):
        sacrificial_ep = sacrificial_op.ep
        target_ep = target_op.ep
        if sacrificial_ep is None or target_ep is None:
            self._clear_pump_state(target_op)
            return

        name = f"PUMP_PURIFY({target_op.n1.name}-{target_op.n2.name})-step{target_op.pump_step + 1}"
        purify_op = Operation(
            name=name,
            type=OpType.PURIFY,
            n1=target_op.n1,
            n2=target_op.n2,
            status=OpStatus.READY,
            children=[target_op],
            pur_eps=[sacrificial_ep, target_ep],
            request=target_op.request,
            parent_swap=target_op.parent_swap,
        )
        self.pumping_ops.append(purify_op)
        self.pump_op_target[purify_op] = target_op

    def _on_pump_purify_done(
        self,
        purify_op: Operation,
        target_op: Operation,
        success: bool,
        target_ep: EP | None,
        new_fid: float | None,
    ):
        if not success or target_ep is None:
            self._clear_pump_state(target_op)
            return

        target_op.pump_step += 1
        if target_ep.owner_op is purify_op:
            target_ep.change_owner(pre_owner=purify_op, new_owner=target_op)
        target_op.ep = target_ep
        if self._should_stop_pumping(target_op):
            self._clear_pump_state(target_op)
            return
        self._schedule_pump_gen_link(target_op=target_op)

    def _advance_pumping_ops(self):
        if not self.pumping_ops:
            return

        for op in list(self.pumping_ops):
            target = self.pump_op_target.get(op)
            if target is not None and self._should_stop_pumping(target):
                self._clear_pump_state(target)
                self._cleanup_pump_op(op)
                continue
            if op.status == OpStatus.READY:
                req = target.request if target is not None else None
                self._run_op(req, op)

    def _cleanup_pump_op(self, op: Operation):
        if op in self.pumping_ops:
            self.pumping_ops.remove(op)
        self.pump_op_target.pop(op, None)

    def _clear_pump_state(self, target_op: Operation):
        for op, tgt in list(self.pump_op_target.items()):
            if tgt is target_op:
                if op.ep is not None and op.ep.owner_op is op:
                    self.consume_EP(op.ep)
                self._cleanup_pump_op(op)
        target_op.is_pump_target = False
        target_op.parent_swap = None
        if target_op.ep is None:
            target_op.pump_step = 0

    def gen_single_EP(
        self,
        src: QNode,
        dest: QNode,
        fidelity: float,
        t: Time,
        qc: NewQC | None = None,
        is_free: bool = True,
    ) -> EP | None:
        # リンク(NewQC)単位のメモリ制約で管理する
        if qc is not None and not qc.has_free_memory:
            return None

        if qc is not None:
            qc.use_single_memory()

        link = EP(
            fidelity=fidelity,
            nodes=(src, dest),
            qc=qc,
            created_at=t,
            is_free=is_free,
        )
        self.links.append(link)
        return link

    def decoherence_EP(self, ep: EP):
        # デコヒーレンスによってLinkEPが切り捨てられるとき
        owner = ep.owner_op
        if owner:
            owner.request_regen()
            ep.free_owner(owner)
        self.delete_EP(ep)

    def consume_EP(self, ep: EP):
        # opの実行によってLinkEPが消費されるとき
        # opの所有epから消す
        assert ep.owner_op is not None
        ep.free_owner(pre_owner=ep.owner_op)
        self.delete_EP(ep=ep)

    def delete_EP(self, ep: EP):
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
