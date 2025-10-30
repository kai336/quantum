# link.py
from qns.entity.node.node import QNode
from qns.entity import Entity
from qns.network.protocol.entanglement_distribution import QuantumChannel
from qns.simulator import Time
from typing import Tuple


class LinkEP(Entity):
    """
    １つの link = bell pair を記述するクラス
    """

    def __init__(
        self,
        name: str = None,
        fidelity: float = 0,
        nodes: Tuple[QNode, QNode] = None,
        qc: QuantumChannel = None,
        created_at: Time = None,
        status: str = None,
        swap_level: int = 0,  # 何回のswapでできているか
    ):
        super().__init__(name=name)
        self.fidelity = fidelity
        self.nodes = nodes

    def write_status(self, status: str):
        self.status = status

    def get_status(self):
        return self.status

    def __repr__(self) -> str:
        if self.name is not None:
            return f"<LinkEP {self.name}>"
        return super().__repr__()
