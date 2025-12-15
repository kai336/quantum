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
        delay: float = 0,
        fidelity_init: float = 0.99,
        memory_capacity: int = 5,
    ):
        super().__init__(
            name=name,
            node_list=node_list,
            bandwidth=bandwidth,
            delay=delay,
            length=length,
        )
        self.fidelity_init = fidelity_init
        self.memory_capacity = memory_capacity
        self.memory_usage = 0

    @property
    def has_free_memory(self) -> bool:
        return self.memory_usage < self.memory_capacity

    def use_single_memory(self):
        assert self.has_free_memory
        self.memory_usage += 1

    def free_single_memory(self):
        if self.memory_usage > 0:
            self.memory_usage -= 1
