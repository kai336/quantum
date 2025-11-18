from enum import Enum, auto
from typing import List, Optional
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
        parent: Optional["OP"] = None,
        children: Optional[List["OP"]] = None,
    ):
        self.name = name
        self.op = op
        self.status = OpStatus.WAITING
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
