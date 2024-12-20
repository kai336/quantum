#purification and swapping
from typing import Dict, Optional
import uuid

from qns.entity.cchannel.cchannel import ClassicChannel, ClassicPacket, RecvClassicPacket
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel, RecvQubitPacket
from qns.models.core.backend import QuantumModel
from qns.network.requests import Request
from qns.simulator.event import Event, func_to_event
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
from qns.models.epr import WernerStateEntanglement
from qns.simulator.ts import Time
import qns.utils.log as log

class PSApp(Application):
    def __init__(self,
                init_fidelity: float = 0.99,
                p_gen: float = 0.8,
                p_swap: float = 0.8,
                p_purification = 0.8,
                send_rate: Optional[int] = None):
        super().__init__()
        self.init_fidelity = init_fidelity
        self.p_gen = p_gen
        self.p_swap = p_swap
        self.p_purification = p_purification
        self.send_rate = send_rate

        self.net: QuantumNetwork = None
        self.own: QNode = None
        self.memory: QuantumMemory = None

        self.success = []
        self.send_count = 0
