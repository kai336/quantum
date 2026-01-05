# controller_app.py
# main duty: controll the entire network
import logging
import math
import random
from collections import deque
from os import name
from typing import DefaultDict, Deque, Dict, List, Optional

import qns.utils.log as log
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.network import QuantumNetwork
from qns.network.topology.waxmantopo import QuantumChannel
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
CLASSICAL_LIGHT_SPEED = 2e8  # m/s 相当（伝送遅延近似用）


class PSWRequest:
    """PSW用の簡易リクエストコンテナ。"""

    def __init__(
        self,
        *,
        name: str,
        swap_plan: tuple[Operation, list[Operation]],
        target_op: Operation,
    ):
        self.name = name
        self.swap_plan = swap_plan
        self.target_op = target_op
        self.is_done: bool = False
        self.is_psw: bool = True


class ControllerApp(Application):
    """
    ネットワーク全体を制御(EP生成、スワップ計画、リクエスト管理)
    """

    def __init__(
        self,
        p_swap: float = p_swap,
        # p_pur: float = p_pur,
        gen_rate: int = gen_rate,
        t_mem: float = 1.0,
        f_req=f_req,
        f_cut=f_cut,
        init_fidelity: float = init_fidelity,
        enable_psw: bool = True,
        psw_threshold: Optional[float] = None,
    ):
        super().__init__()
        self.p_swap: float = p_swap
        # self.p_pur: float = p_pur
        self.gen_rate: int = gen_rate
        self.f_req: float = f_req
        self.f_cut: float = f_cut
        self.t_mem = t_mem
        self.init_fidelity: float = init_fidelity
        # swap待機中に忠実度が閾値を下回ったら1回だけpurifyするPSW(Purify-while-Swap-waiting)
        self.enable_psw: bool = enable_psw
        # NoneならPSW無効。指定がなければf_cutより少し高い値を既定にする
        self.psw_threshold: Optional[float] = (
            psw_threshold if psw_threshold is not None else f_cut + 0.05
        )
        self.net: QuantumNetwork
        self.node: QNode
        self.requests: List[NewRequest] = []
        self.links: List[EP] = []  # シンプルにlinkEPぶち込んでEP管理
        self.links_next: List[EP] = []  # 次のタイムスロットで使えるようになる新EP
        # self.fidelity: List[float] = []  # i番目のqcで生成されるlinkのフィデリティ初期値
        self.nodes: List[QNode] | None = None
        self.completed_requests: List[dict] = []
        self.gen_interval_slot: int
        self._next_gen_time_slot: int | None = (
            None  # gen_rateに応じてリンクレベルEP生成するため
        )
        # PSW用にアドホックなオペレーションを管理
        self.psw_op_target: Dict[Operation, Dict[str, object]] = {}
        self.psw_groups: Dict[Operation, Dict[str, object]] = {}
        # PSWの統計
        self.psw_gen_link_scheduled: int = 0
        self.psw_purify_scheduled: int = 0
        self.psw_purify_success: int = 0
        self.psw_purify_fail: int = 0
        self.psw_cancelled: int = 0
        # swap待機時間の集計用
        self.swap_wait_times: List[int] = []
        self.swap_wait_times_by_req: Dict[str, List[int]] = {}
        # gen_link -> gen_EP_routineで生成するqcリスト dict[qc_name, [op待ち行列]]
        self.genlink_queue: dict[str, deque[Operation]] = {}
        self.qc_by_name: Dict[str, NewQC] = {}

    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.node = node
        assert isinstance(node.network, QuantumNetwork)
        self.net = node.network
        self.gen_interval_slot = self._calc_gen_interval_slot()

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
        self._next_gen_time_slot = t.time_slot
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
                src=src, dest=dest, name=name, priority=0, f_req=self.f_req
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
                log.logger.debug(
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
            qc_name = qc.name
            node_list = qc.node_list
            new_qc = NewQC(
                name=qc_name,
                node_list=node_list,
                fidelity_init=fidelity_init,
                memory_capacity=l0_link_max,
                length=qc.length,
            )
            new_qcs.append(new_qc)

        self.new_qcs = new_qcs
        self.genlink_queue = {qc.name: deque() for qc in self.new_qcs}
        self.qc_by_name = {qc.name: qc for qc in self.new_qcs}

    def gen_EP_routine(self):
        # 全チャネルでリンクレベルもつれ生成x
        # ->gen_link opから要求のあったものだけ生成

        # 次のイベント挿入
        self._add_next_tick_event(fn=self.request_handler_routine)

        # gen_rateの間隔をみてまだならreturn
        tc = self._simulator.tc
        if self._next_gen_time_slot is None:
            self._next_gen_time_slot = tc.time_slot
        if tc.time_slot < self._next_gen_time_slot:
            return

        log.logger.debug(f"{self._simulator.tc} gen ep routine start")

        # pending demandsからEP生成
        for qc_name, queue in list(self.genlink_queue.items()):
            if not queue:
                continue
            qc = self.qc_by_name[qc_name]
            assert qc is not None, f"no QC named {qc_name}"
            if not qc.has_free_memory:
                continue
            op = queue.popleft()
            nodes = qc.node_list
            ep = self.gen_single_EP(
                src=nodes[0],
                dest=nodes[1],
                fidelity=qc.fidelity_init,
                t=tc,
                qc=qc,
            )
            if ep is None:
                queue.appendleft(op)  # queueの先頭に戻す
                continue
            # gen_linkをdoneにする
            op.ep = ep
            ep.set_owner(op)
            op.done()
            op.demand_registered = False  # 再生成のために解除

        # 次回の生成時刻を更新
        self._next_gen_time_slot += self.gen_interval_slot

    def _find_qc_by_nodes(self, n1: QNode, n2: QNode) -> Optional[NewQC]:
        for qc in self.new_qcs:
            if set(qc.node_list) == {n1, n2}:
                return qc
        return None

    def request_handler_routine(self):
        # リクエストを管理
        # req.swap_plan, req.swap_progressから各操作を実行

        # 次のイベント挿入
        self._add_next_tick_event(fn=self.links_manager_routine)

        log.logger.debug(f"{self._simulator.tc} req routine start")
        is_all_done = True
        for req in self.requests:
            if req.swap_plan is None:
                if not req.is_done:
                    log.logger.debug(f"skip request without swap plan: {req.name}")
                    req.is_done = True
                continue

            # 終了判定
            root_op, ops = req.swap_plan
            assert isinstance(root_op, Operation)
            idx = self.requests.index(req)
            if req.is_done:
                # print("!!!!!!!!req", idx, " finished!!!!!!!!")
                continue
            elif root_op.status == OpStatus.DONE and (
                getattr(req, "is_psw", False)
                or (root_op.ep and root_op.ep.fidelity >= self.f_req)
            ):
                # f_reqも終了条件に加える
                req.is_done = True
                if not getattr(req, "is_psw", False):
                    finish_time = self._simulator.tc.time_slot
                    self.completed_requests.append(
                        {
                            "index": idx,
                            "name": req.name,
                            "finish_time": finish_time,
                            "fidelity": root_op.ep.fidelity,
                        }
                    )
                    log.logger.debug(
                        f"!!!!!!!!req {idx} finished!!!!!!!! fid: {root_op.ep.fidelity}"
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

    def links_manager_routine(self):
        # self.linksからLinkEPのデコヒーレンスを管理
        # self.links_next　を次のタイムスロットでself.linksに挿入
        log.logger.debug(f"{self._simulator.tc} link routine start")

        if len(self.links_next) != 0:
            self.links += self.links_next

        # print("links: ", [link.fidelity for link in self.links])
        dt = Time(time_slot=3).sec  # 1 timeslotをsec単位に変換
        for link in list(self.links):  # 途中でリンクが削除されても安全に回す
            self.fid_update_EP(ep=link, dt=dt)  # フィデリティ更新
            if link.fidelity < self.f_cut:  # f_cut以下のもつれを切り捨てる
                log.logger.info(f"{self._simulator.tc} decoherenced link {link.nodes}")
                self.decoherence_EP(link)
        if self.enable_psw and self.psw_threshold is not None:
            self._scan_psw_targets()
        self.links_next.clear()

        self._add_next_tick_event(fn=self.gen_EP_routine)

    def _advance_request(
        self, req: NewRequest, root_op: Operation, ops: List[Operation]
    ):
        # リクエストを１操作分進める
        # 現時点でREADYなopだけ実行
        ready_ops = [op for op in ops if op.status == OpStatus.READY]
        for op in ready_ops:  # コピー使うことで1操作分以上進まないようにする
            log.logger.debug(f"{self._simulator.tc} {op} start op")
            self._run_op(req, op)

    def _run_op(self, req: Optional[NewRequest], op: Operation):
        # 操作を実行
        log.logger.debug(f"{self._simulator.tc} run op={op} type={op.type.name}")
        op.start()
        if op.type == OpType.GEN_LINK:
            self._handle_gen_link(op)
        elif op.type == OpType.SWAP:
            self._handle_swap(op, req)
        elif op.type == OpType.PURIFY:
            self._handle_purify(op)

    def _record_swap_waiting(
        self,
        *,
        ep_left: Optional[EP],
        ep_right: Optional[EP],
        req: Optional[NewRequest],
    ) -> None:
        """swap実行時の待機時間を記録する。"""

        def _wait_slots(ep: Optional[EP]) -> Optional[int]:
            if ep is None or ep.created_at is None:
                return None
            return self._simulator.tc.time_slot - ep.created_at.time_slot

        waits: List[int] = []
        for ep in (ep_left, ep_right):
            wait_slot = _wait_slots(ep)
            if wait_slot is not None:
                waits.append(wait_slot)

        if waits:
            self.swap_wait_times.extend(waits)
            if req is not None:
                bucket = self.swap_wait_times_by_req.setdefault(req.name, [])
                bucket.extend(waits)

    def _handle_gen_link(self, op: Operation):
        # 生成済みEPを探すx
        # ->リンクEPの生成を要求する
        self._register_link_demand(op)

        # pair = set((op.n1, op.n2))
        # ep_cand: Optional[EP] = None
        # for link in self.links:
        #     if set(link.nodes) == pair and link.is_free:
        #         ep_cand = link
        #         break
        # if ep_cand is None:
        #     # まだEPなし
        #     log.logger.debug(f"{self._simulator.tc} no link")
        #     op.request_regen()  # 再試行できるようREADYに戻す
        #     return

        # log.logger.debug(f"{self._simulator.tc} gen link success op={op}")
        # ep_cand.set_owner(op)
        # op.done()
        # meta = self.psw_op_target.get(op)
        # if meta is not None and meta.get("role") == "sacrificial":
        #     target = meta.get("target")
        #     self._cleanup_psw_group(op)
        #     if target is not None:
        #         self._on_psw_sacrificial_ready(sacrificial_op=op, target_op=target)

    def _register_link_demand(self, op: Operation) -> NewQC:
        # gen_linkによるリンクレベルEP生成の要求登録
        qc = self._find_qc_by_nodes(op.n1, op.n2)
        assert qc is not None, f"no QC for GEN_LINK: {op.n1.name}-{op.n2.name}"
        if not op.demand_registered:
            self.genlink_queue[qc.name].append(op)
            op.demand_registered = True
        op.status = OpStatus.WAITING
        return qc

    def _handle_swap(self, op: Operation, req: Optional[NewRequest] = None):
        # swap
        ep_left = op.children[0].ep
        ep_right = op.children[1].ep
        if ep_left is None or ep_right is None:
            # 必要なEPがデコヒーレンス等で欠落したら再生成を要求する
            log.logger.debug(f"{self._simulator.tc} swap missing ep op={op}")
            op.request_regen()
            return
        if ep_left not in self.links or ep_right not in self.links:
            if ep_left in self.links_next or ep_right in self.links_next:
                op.status = OpStatus.READY
                return
            # 必要なEPがデコヒーレンス等で欠落したら再生成を要求する
            log.logger.debug(f"{self._simulator.tc} swap missing ep op={op}")
            op.request_regen()
            return

        # 一応中間ノードの整合性チェック
        via = op.via
        assert via is not None
        assert via in ep_left.nodes and via in ep_right.nodes

        # 先にもとのもつれを廃棄しとく
        # 失敗・成功にかかわらずもとのもつれは使えない　& 新たにメモリ消費することなくswapできるので
        len_left = ep_left.qc.length if ep_left.qc else 0.0
        len_right = ep_right.qc.length if ep_right.qc else 0.0
        self._record_swap_waiting(
            ep_left=ep_left,
            ep_right=ep_right,
            req=req,
        )
        self.consume_EP(ep_left)
        self.consume_EP(ep_right)

        # swap
        if random.random() < self.p_swap:
            # 新しいEP生成
            new_fid = f_swap(ep_left.fidelity, ep_right.fidelity)
            tc = self._simulator.tc
            delay_slot = self._calc_delay_slots(max(len_left, len_right))
            t_done = tc.__add__(Time(time_slot=delay_slot))
            event = func_to_event(
                t=t_done,
                fn=lambda op=op, fid=new_fid: self._finish_swap(op=op, fidelity=fid),
                by=self,
            )
            self._simulator.add_event(event)
            log.logger.debug(
                f"{self._simulator.tc} swap scheduled op={op} delay_slot={delay_slot}"
            )
        else:
            # 再生成要求
            log.logger.debug(f"{self._simulator.tc} swap failed op={op}")
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
        length = ep_target.qc.length if ep_target.qc else 0.0

        self.consume_EP(ep_sacrifice)  # どっちにしろ犠牲になるのでfidも取ったし消しとく
        new_fid = f_pur(ft=fid_target, fs=fid_sacrifice)  # purify成功後のfidelity

        op.pur_eps.clear()
        success_prob = p_pur(ft=fid_target, fs=fid_sacrifice)
        delay_slot = self._calc_delay_slots(length)
        tc = self._simulator.tc
        t_done = tc.__add__(Time(time_slot=delay_slot))
        event = func_to_event(
            t=t_done,
            fn=lambda op=op,
            ep=ep_target,
            fid=new_fid,
            prob=success_prob: self._finish_purify(  # noqa: E501
                op=op, ep_target=ep, new_fid=fid, success_prob=prob
            ),
            by=self,
        )
        self._simulator.add_event(event)
        log.logger.debug(
            f"{self._simulator.tc} purify scheduled op={op} delay_slot={delay_slot}"
        )
        assert len(op.pur_eps) == 0

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
        self.links_next.append(link)
        return link

    def fid_update_EP(self, ep: EP, dt: float):
        # 時間経過によるフィデリティ更新
        f = ep.fidelity
        alpha: float = math.exp(-dt / self.t_mem)
        f_new: float = 1 / 4 + alpha * (f - 1 / 4)
        ep.fidelity = f_new

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
        if ep in self.links:
            self.links.remove(ep)
        elif ep in self.links_next:
            self.links_next.remove(ep)
        del ep

    def _add_next_tick_event(self, fn):
        t_tick = Time(time_slot=1)
        tc = self._simulator.tc
        tn = tc.__add__(t_tick)
        next_event = func_to_event(t=tn, fn=fn, by=self)
        self._simulator.add_event(next_event)

    def _calc_gen_interval_slot(self) -> int:
        if self.gen_rate <= 0:
            log.logger.debug(
                "gen_rateが0以下のため、生成間隔をデフォルト1タイムスロットに設定します"
            )
            return 1
        t = 1 / self.gen_rate
        interval = Time(sec=t, accuracy=self._simulator.accuracy)
        if interval.time_slot <= 0:
            return 1

        return interval.time_slot

    # --- PSW: swap待機中の閾値ピュリフィケーション（単発） ---
    def _is_swap_waiting(self, op_child: Operation) -> bool:
        op_parent = op_child.parent
        if op_parent is None or op_parent.type != OpType.SWAP:
            return False
        assert len(op_parent.children) == 2
        left = op_parent.children[0]
        right = op_parent.children[1]
        other = right if op_child is left else left
        return other.ep is None

    def _psw_waiting_ep(self, op: Operation) -> Optional[EP]:
        """PSW対象のopが「片側だけEPありで待機中」なら、そのEPを返す。"""
        if op.type == OpType.GEN_LINK:
            return op.ep
        if op.type == OpType.SWAP:
            if len(op.children) < 2:
                return None
            ep_left = op.children[0].ep
            ep_right = op.children[1].ep
            eps = [ep for ep in (ep_left, ep_right) if ep is not None]
            return eps[0] if len(eps) == 1 else None
        if op.type == OpType.PURIFY:
            if len(op.pur_eps) < 2:
                return None
            eps = [ep for ep in op.pur_eps if ep is not None]
            return eps[0] if len(eps) == 1 else None
        return None

    def _is_psw_waiting(self, op: Operation) -> bool:
        """PSW対象になり得る待機中かどうか。"""
        return self._psw_waiting_ep(op) is not None

    def _scan_psw_targets(self):
        if not self.enable_psw or self.psw_threshold is None:
            return
        for req in self.requests:
            if getattr(req, "is_psw", False):
                continue
            if req.swap_plan is None:
                continue
            _, ops = req.swap_plan
            for op in ops:
                if op.threshold_purified:
                    continue
                waiting_ep = self._psw_waiting_ep(op)
                if waiting_ep is None:
                    continue
                if waiting_ep.fidelity >= self.psw_threshold:
                    continue
                if self._has_pending_psw(op):
                    continue
                parent_type = op.parent.type.name if op.parent is not None else "NONE"
                log.logger.info(
                    f"{self._simulator.tc} PSW target found op={op} parent={parent_type} fid={waiting_ep.fidelity:.3f} threshold={self.psw_threshold}"  # noqa: E501
                )
                self._schedule_psw_op(target_op=op)

    def _has_pending_psw(self, target_op: Operation) -> bool:
        return any(
            meta.get("target") is target_op for meta in self.psw_op_target.values()
        )

    def _clone_psw_tree(self, op: Operation) -> List[Operation]:
        ops: List[Operation] = []

        def _clone(node: Operation, parent: Optional[Operation] = None) -> Operation:
            status = (
                OpStatus.READY if node.type == OpType.GEN_LINK else OpStatus.WAITING
            )
            clone = Operation(
                name=f"PSW_{node.name}",
                type=node.type,
                n1=node.n1,
                n2=node.n2,
                via=node.via,
                status=status,
                parent=parent,
                children=[],
                request=node.request,
            )
            ops.append(clone)
            for child in node.children:
                child_clone = _clone(child, parent=clone)
                clone.children.append(child_clone)
            return clone

        _clone(op)
        return ops

    def _register_psw_group(
        self,
        *,
        root_op: Operation,
        ops: List[Operation],
        target_op: Operation,
        role: str,
        psw_req: PSWRequest,
    ) -> None:
        self.psw_groups[root_op] = {"ops": ops, "request": psw_req}
        self.psw_op_target[root_op] = {
            "target": target_op,
            "role": role,
            "request": psw_req,
        }

    def _cleanup_psw_group(self, root_op: Operation) -> None:
        info = self.psw_groups.pop(root_op, {})
        ops = info.get("ops", [])
        psw_req: PSWRequest | None = info.get("request")
        for op in ops:
            self.psw_op_target.pop(op, None)
        # 同じPSWリクエストを指す他のグループもまとめて掃除
        if psw_req:
            for key, val in list(self.psw_groups.items()):
                if val.get("request") is psw_req:
                    self.psw_groups.pop(key, None)
                    for op in val.get("ops", []):
                        self.psw_op_target.pop(op, None)
        if psw_req:
            psw_req.is_done = True
            if psw_req in self.requests:
                self.requests.remove(psw_req)

    def _schedule_psw_op(self, target_op: Operation):
        target_op.threshold_purified = True  # 今回の待ち時間では1回だけ
        ops = self._clone_psw_tree(target_op)
        root_op = ops[0]
        psw_req = PSWRequest(
            name=f"PSW_{target_op.name}",
            swap_plan=(root_op, ops),
            target_op=target_op,
        )
        for op in ops:
            op.request = psw_req
        self.requests.append(psw_req)
        log.logger.info(
            f"{self._simulator.tc} PSW schedule target={target_op} root={root_op}"
        )
        self._register_psw_group(
            root_op=root_op,
            ops=ops,
            target_op=target_op,
            role="sacrificial",
            psw_req=psw_req,
        )
        self.psw_gen_link_scheduled += 1

    def _on_psw_sacrificial_ready(
        self, sacrificial_op: Operation, target_op: Operation
    ):
        sacrificial_ep = sacrificial_op.ep
        target_ep = self._psw_waiting_ep(target_op)
        if (
            sacrificial_ep is None
            or target_ep is None
            or not self._is_psw_waiting(target_op)
        ):
            log.logger.info(
                f"{self._simulator.tc} PSW cancelled before purify target={target_op}"
            )
            if sacrificial_ep is not None:
                self.consume_EP(sacrificial_ep)
            target_op.threshold_purified = False
            self.psw_cancelled += 1
            return
        log.logger.info(
            f"{self._simulator.tc} PSW purify start target={target_op} target_fid={target_ep.fidelity:.3f} sacrificial_fid={sacrificial_ep.fidelity:.3f}"  # noqa: E501
        )
        name = f"PSW_PURIFY({target_op.n1.name}-{target_op.n2.name})"
        purify_op = Operation(
            name=name,
            type=OpType.PURIFY,
            n1=target_op.n1,
            n2=target_op.n2,
            status=OpStatus.READY,
            children=[target_op],
            pur_eps=[sacrificial_ep, target_ep],
            request=target_op.request,
        )
        sacrificial_ep.change_owner(pre_owner=sacrificial_op, new_owner=purify_op)
        # PSWリクエストへ統合
        meta = self.psw_op_target.get(sacrificial_op) or {}
        psw_req: PSWRequest | None = meta.get("request")
        if psw_req is None:
            # 安全策：既存ターゲットのリクエストを利用
            psw_req = PSWRequest(
                name=f"PSW_{target_op.name}_purify",
                swap_plan=(purify_op, [purify_op]),
                target_op=target_op,
            )
            self.requests.append(psw_req)
        purify_op.request = psw_req
        group_info = self.psw_groups.get(sacrificial_op)
        if group_info:
            group_ops = group_info.get("ops", [])
            group_ops.append(purify_op)
            group_info["ops"] = group_ops
        self.psw_groups[purify_op] = {"ops": [purify_op], "request": psw_req}
        self.psw_op_target[purify_op] = {
            "target": target_op,
            "role": "purify",
            "sacrificial_ep": sacrificial_ep,
            "request": psw_req,
        }
        self.psw_purify_scheduled += 1

    def _advance_psw_ops(self):
        # PSWは通常のリクエストループに統合済み
        return

    def _calc_delay_slots(self, length: float, round_trip: bool = True) -> int:
        distance = length * (2 if round_trip else 1)
        delay_sec = distance / CLASSICAL_LIGHT_SPEED if distance > 0 else 0.0
        slots = math.ceil(delay_sec * self._simulator.accuracy)
        return max(1, slots)

    def _finish_swap(self, op: Operation, fidelity: float):
        if op.status != OpStatus.RUNNING:
            return
        tc = self._simulator.tc
        new_ep = self.gen_single_EP(op.n1, op.n2, fidelity=fidelity, t=tc)
        if new_ep is None:
            op.request_regen()
            return
        new_ep.set_owner(op)
        op.done()
        log.logger.debug(f"{self._simulator.tc} swap success op={op}")
        meta = self.psw_op_target.get(op)
        if meta is not None and meta.get("role") == "sacrificial":
            target = meta.get("target")
            self._cleanup_psw_group(op)
            log.logger.info(
                f"{self._simulator.tc} PSW sacrificial ready op={op} target={target}"
            )
            if target is not None:
                self._on_psw_sacrificial_ready(sacrificial_op=op, target_op=target)

    def _finish_purify(
        self, op: Operation, ep_target: EP, new_fid: float, success_prob: float
    ):
        if op.status != OpStatus.RUNNING:
            return
        # target EPが既に消えていたら再生成要求
        if ep_target not in self.links:
            meta = self.psw_op_target.get(op)
            if meta is not None and meta.get("role") == "purify":
                target = meta.get("target")
                if target is not None:
                    target.threshold_purified = True
                    target.request_regen()
                self._cleanup_psw_group(op)
                self.psw_cancelled += 1
            op.request_regen()
            return

        success = random.random() < success_prob
        if success:
            log.logger.debug(f"{self._simulator.tc} purify success op={op}")
            ep_target.fidelity = new_fid  # fidelity更新
            meta = self.psw_op_target.get(op)
            if meta is not None and meta.get("role") == "purify":
                self.psw_purify_success += 1
                target = meta.get("target")
                if target is not None:
                    if ep_target.owner_op is op:
                        ep_target.change_owner(pre_owner=op, new_owner=target)
                    target.ep = ep_target
                    target.threshold_purified = True
                self._cleanup_psw_group(op)
                log.logger.info(
                    f"{self._simulator.tc} PSW purify success op={op} target={target}"
                )
                op.done()
            elif meta is not None and meta.get("role") == "sacrificial":
                target = meta.get("target")
                if ep_target.owner_op is not op:
                    pre = op.children[0]
                    ep_target.change_owner(pre_owner=pre, new_owner=op)
                op.done()
                self._cleanup_psw_group(op)
                if target is not None:
                    self._on_psw_sacrificial_ready(sacrificial_op=op, target_op=target)
            else:
                if ep_target.owner_op is not op:
                    pre = op.children[0]
                    ep_target.change_owner(pre_owner=pre, new_owner=op)
                op.done()
        else:
            log.logger.debug(f"{self._simulator.tc} purify failed op={op}")
            self.consume_EP(ep_target)
            meta = self.psw_op_target.get(op)
            if meta is not None and meta.get("role") == "purify":
                self.psw_purify_fail += 1
                target = meta.get("target")
                if target is not None:
                    target.threshold_purified = True
                    target.request_regen()
                self._cleanup_psw_group(op)
                log.logger.info(
                    f"{self._simulator.tc} PSW purify failed op={op} target={target}"
                )
                op.request_regen()
            else:
                op.request_regen()
