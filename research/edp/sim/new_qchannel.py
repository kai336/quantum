# new_qnet.py
# QuantumChannelに生成されるEPの初期fidelityを追加

from typing import List
from qns.entity.node import QNode
from qns.entity.qchannel import QuantumChannel


class NewQC(QuantumChannel):
    def __init__(
        self,
        name: str = None,
        node_list: List[QNode] = ...,
        bandwidth: int = 0,
        length: float = 0,
        fidelity_init: float = 0.99,
    ):
        super().__init__(
            name,
            node_list,
            bandwidth,
            length,
        )
        self.fidelity_init = fidelity_init
