from qns.entity.qchannel.qchannel import QuantumChannel as OriginalQC
from qns.models.delay.delay import DelayModel
from qns.entity.node.node import QNode
from qns.simulator.ts import Time
from typing import List, Dict

class QuantumChannel(OriginalQC):
    def __init__(self, name: str = None, node_list: List[QNode] = [], bandwidth: int = 0, delay: float | DelayModel = 0, drop_rate: float = 0, max_buffer_size: int = 0, length: float = 0, decoherence_rate: float | None = 0, transfer_error_model_args: Dict = {}, reservation: int = -1, is_entangled: bool = False, born: Time = None):
        super().__init__(name, node_list, bandwidth, delay, drop_rate, max_buffer_size, length, decoherence_rate, transfer_error_model_args)

        self.reservation = reservation # index of request
        self.is_entangled = is_entangled
        self.born = born