# swap, purify等の操作を扱うクラス
# swapping treeを構成するノード
from enum import Enum, auto
from typing import List, Optional, Tuple

from qns.entity.node import QNode

from edp.sim.link import LinkEP


class OpType(Enum):
    SWAP = auto()
    PURIFY = auto()
    GEN_LINK = auto()


class OpStatus(Enum):
    WAITING = auto()
    READY = auto()
    RUNNING = auto()
    DONE = auto()
    RETRY = auto()


class Operation:
    def __init__(
        self,
        name: str,
        type: OpType,
        n1: QNode,
        n2: QNode,
        via: Optional[QNode] = None,
        status: Optional[OpStatus] = None,
        parent: Optional["Operation"] = None,
        children: Optional[List["Operation"]] = None,
        ep: Optional[LinkEP] = None,
        pur_eps: List[LinkEP] = [],
    ):
        self.name = name
        self.type = type
        self.status = status or OpStatus.WAITING
        self.n1 = n1
        self.n2 = n2
        self.via = via
        self.parent = parent
        self.children = children or []
        self.ep = ep  # この操作が完了した後にできるもつれ
        self.pur_eps = pur_eps or []

    def is_leaf(self) -> bool:
        # 自分が葉ノードかどうか
        return len(self.children) == 0

    def can_run(self) -> bool:
        # 自分が実行可能かどうか
        if self.is_leaf():
            return True
        return all(ch.status == OpStatus.DONE for ch in self.children)

    def judge_ready(self):
        # 自分が準備完了かどうか
        # purifyの場合
        # 子ノードが完了したときにこの関数が呼ばれる
        if self.type == OpType.PURIFY:
            self._judge_ready_purify()
        # purify以外
        elif self.can_run() and self.status in (OpStatus.WAITING, OpStatus.RETRY):
            self.status = OpStatus.READY

    def _judge_ready_purify(self):
        # self.pur_epsの数で判定
        # pur_epsは更新前
        # 子のEPの所有権を自分に移す
        num_eps = len(self.pur_eps)
        op_child = self.children[0]
        ep_child = op_child.ep
        assert ep_child is not None
        ep_child.change_owner(pre_owner=op_child, new_owner=self)
        assert isinstance(ep_child, LinkEP)
        self.pur_eps.append(ep_child)

        if num_eps == 0:
            # targetEPができたのでsacrifice用に子だけ再実行を要求
            self.status = OpStatus.WAITING
            for c in self.children:
                c.request_regen()
        elif num_eps == 1:
            # sacrificeEPができた
            self.status = OpStatus.READY

    def start(self):
        # 実行開始
        self.status = OpStatus.RUNNING

    def done(self):
        # 実行完了して親に伝える or req完了を伝える
        self.status = OpStatus.DONE
        if self.parent:
            self.parent.judge_ready()

    def failed(self):
        self.status = OpStatus.WAITING
        self.ep = None
        # request_regenでいい

    def request_regen(self):
        # このOPに必要なEPを再生成
        self.ep = None
        self.pur_eps.clear()
        if not self.is_leaf():
            self.status = OpStatus.RETRY
            for c in self.children:
                c.request_regen()
        else:  # 葉で再帰とめる
            self.status = OpStatus.READY

    def __repr__(self) -> str:
        return f"{self.name}"
        # return f"OP(name={self.name}, op={self.op.name}, nodes={self.n1, self.n2, self.via} status={self.status.name})"


def build_ops_from_edp_result(
    edp_result: Tuple[float, dict],
) -> Tuple[Operation, List[Operation]]:
    """
    EDP が返した (latency, tree_dict) から
    OP インスタンスの配列を作って返す
    """
    _, tree = edp_result
    ops: List[Operation] = []
    root: Operation | None = None

    def _build(node_dict: dict, parent: Operation | None = None) -> Operation:
        nonlocal root
        node_type = node_dict["type"]

        if node_type == "Link":
            n1, n2 = node_dict["link"]
            op = Operation(
                name=f"GEN_LINK({n1.name}-{n2.name})",
                type=OpType.GEN_LINK,
                status=OpStatus.READY,  # ここでGENLINKをあらかじめ実行できるようにしとく
                n1=n1,
                n2=n2,
                via=None,
                parent=parent,
                children=[],
            )

        elif node_type == "Swap":
            via = node_dict["via"]
            x = node_dict["x"]
            y = node_dict["y"]

            op = Operation(
                name=f"SWAP({x.name}-{via.name}-{y.name})",
                type=OpType.SWAP,
                n1=x,
                n2=y,
                via=via,
                parent=parent,
                children=[],
            )

            left_child = _build(node_dict["left"], parent=op)
            right_child = _build(node_dict["right"], parent=op)
            op.children = [left_child, right_child]

        elif node_type == "Purify":
            x = node_dict["x"]
            y = node_dict["y"]

            op = Operation(
                name=f"PURIFY({x.name}-{y.name})",
                type=OpType.PURIFY,
                n1=x,
                n2=y,
                parent=parent,
                children=[],
            )

            child_op = _build(node_dict["child"], parent=op)
            op.children = [child_op]

        else:
            raise ValueError(f"Unknown node type: {node_type}")

        if parent is None and root is None:
            root = op
        ops.append(op)
        # print(f"{op.name}, {op.parent}")
        return op

    _build(tree, parent=None)
    assert root is not None
    return root, ops
