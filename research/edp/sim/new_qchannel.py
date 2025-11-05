# new_qnet.py
# QuantumChannelに生成されるEPの初期fidelityを追加

from qns.entity.qchannel import QuantumChannel


class NewQC(QuantumChannel):
    def __init__(
        self,
        name: str = None,
        node_list: List[QNode] = ...,
        bandwidth: int = 0,
        delay: Union[float, DelayModel] = 0,
        drop_rate: float = 0,
        max_buffer_size: int = 0,
        length: float = 0,
        decoherence_rate: Optional[float] = 0,
        transfer_error_model_args: dict = ...,
        fidelity_init: float = 0.99,
    ):
        super().__init__(
            name,
            node_list,
            bandwidth,
            delay,
            drop_rate,
            max_buffer_size,
            length,
            decoherence_rate,
            transfer_error_model_args,
        )
        self.fidelity_init = fidelity_init
