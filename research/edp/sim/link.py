# link.py
import uuid
from typing import TYPE_CHECKING, Optional, Tuple

from qns.entity import Entity
from qns.entity.node.node import QNode
from qns.entity.qchannel import QuantumChannel
from qns.simulator import Time

from edp.sim.models import f_link

if TYPE_CHECKING:
    from edp.sim.op import Operation


class LinkEP(Entity):
    """
    １つの link = bell pair を記述するクラス リンクレベルのリンクとは違う意味なのでややこしい
    name(uuid), fidelity, nodes, qc, created_at, is_used, swap_level
    """

    def __init__(
        self,
        nodes: Tuple[QNode, QNode],
        name: Optional[str] = None,
        fidelity: float = 0,
        qc: Optional[QuantumChannel] = None,
        created_at: Optional[Time] = None,
        is_free: bool = True,
        owner_op: Optional["Operation"] = None,
        swap_level: int = 0,  # 何回のswapでできているか ここ０ならリンクレベルEP 未実装
    ):
        super().__init__(name=name or str(uuid.uuid4()))
        self.fidelity = fidelity
        self.nodes = nodes
        self.qc = qc
        self.created_at = created_at
        self.is_free = is_free
        self.owner_op = owner_op
        self.swap_level = swap_level

    def change_owner(self, pre_owner: "Operation", new_owner: "Operation"):
        # controller.linksで追跡したまま(deepcopyすることなく)所有者(op)を変えたい
        # owner変えて、opも変える
        assert self.owner_op == pre_owner

        self.owner_op = new_owner
        pre_owner.ep = None
        new_owner.ep = self

    def set_owner(self, new_owner: "Operation"):
        # owner設定して、op側も変える
        assert self.owner_op is None

        self.is_free = False
        self.owner_op = new_owner
        new_owner.ep = self

    def free_owner(self, pre_owner: "Operation"):
        assert self.owner_op == pre_owner

        self.is_free = True
        self.owner_op = None
        pre_owner.ep = None

    def decoherence(self, dt: float):
        f = self.fidelity
        f_new = f_link(f=f, dt=dt)
        self.fidelity = f_new

    def __repr__(self) -> str:
        if self.name is not None:
            return f"<LinkEP {self.name}>"
        return super().__repr__()
