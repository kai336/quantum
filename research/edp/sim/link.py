# link.py
import uuid
from typing import Tuple

from qns.entity import Entity
from qns.entity.node.node import QNode
from qns.network.protocol.entanglement_distribution import QuantumChannel
from qns.simulator import Time


class LinkEP(Entity):
    """
    １つの link = bell pair を記述するクラス リンクレベルのリンクとは違う意味なのでややこしい
    name(uuid), fidelity, nodes, qc, created_at, is_used, swap_level
    """

    def __init__(
        self,
        name=None,
        fidelity: float = 0,
        nodes: Tuple[QNode, QNode] = None,
        qc: QuantumChannel = None,
        created_at: Time = None,
        is_free: bool = True,
        swap_level: int = 0,  # 何回のswapでできているか ここ０ならリンクレベルEP
    ):
        super().__init__(name=str(uuid.uuid4()))
        self.fidelity = fidelity
        self.nodes = nodes
        self.qc = qc
        self.created_at = created_at
        self.is_free = is_free
        self.swap_level = swap_level

    def __repr__(self) -> str:
        if self.name is not None:
            return f"<LinkEP {self.name}>"
        return super().__repr__()
