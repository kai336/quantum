# swap, purify等の操作を扱うクラス
from enum import Enum, auto
from typing import List, Optional, Tuple
from qns.entity.node import QNode


class Operation(Enum):
    SWAP = auto()
    PURIFY = auto()
    GEN_LINK = auto()


class OpStatus(Enum):
    WAITING = auto()
    READY = auto()
    RUNNING = auto()
    DONE = auto()


class OP:
    def __init__(
        self,
        name: str,
        op: Operation,
        n1: QNode,
        n2: QNode,
        status: OpStatus = OpStatus.WAITING,
        parent: Optional["OP"] = None,
        children: Optional[List["OP"]] = None,
    ):
        self.name = name
        self.op = op
        self.status = status
        self.n1 = n1
        self.n2 = n2
        self.parent = parent
        self.children = children or []

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def can_run(self) -> bool:
        if self.is_leaf():
            return True
        return all(ch.status == OpStatus.DONE for ch in self.children)

    def judge_ready(self):
        if self.can_run() and self.status == OpStatus.WAITING:
            self.status = OpStatus.READY

    def start(self):
        self.status = OpStatus.RUNNING

    def finish(self):
        self.status = OpStatus.DONE
        if self.parent:
            self.parent.judge_ready()

    def __repr__(self) -> str:
        return f"OP(name={self.name}, op={self.op.name}, status={self.status.name})"


def build_ops_from_edp_result(edp_result: Tuple[float, dict]) -> List[OP]:
    """
    EDP が返した (latency, tree_dict) から
    OP インスタンスの配列を作って返す
    """
    _, tree = edp_result
    ops: List[OP] = []

    def _build(node_dict: dict, parent: OP | None = None) -> OP:
        node_type = node_dict["type"]

        if node_type == "Link":
            n1, n2 = node_dict["link"]
            op = OP(
                name=f"GEN_LINK({n1.name}-{n2.name})",
                op=Operation.GEN_LINK,
                n1=n1,
                n2=n2,
                parent=parent,
                children=[],
            )

        elif node_type == "Swap":
            via = node_dict["via"]
            x = node_dict["x"]
            y = node_dict["y"]

            op = OP(
                name=f"SWAP({x.name}-{via.name}-{y.name})",
                op=Operation.SWAP,
                n1=x,
                n2=y,
                parent=parent,
                children=[],
            )

            left_child = _build(node_dict["left"], parent=op)
            right_child = _build(node_dict["right"], parent=op)
            op.children = [left_child, right_child]

        elif node_type == "Purify":
            x = node_dict["x"]
            y = node_dict["y"]

            op = OP(
                name=f"PURIFY({x.name}-{y.name})",
                op=Operation.PURIFY,
                n1=x,
                n2=y,
                parent=parent,
                children=[],
            )

            child_op = _build(node_dict["child"], parent=op)
            op.children = [child_op]

        else:
            raise ValueError(f"Unknown node type: {node_type}")

        ops.append(op)
        return op

    _build(tree, parent=None)
    return ops
