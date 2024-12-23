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
import random
import numpy as np

# purification and swapping

class PSApp(Application):
    def __init__(self,
                init_fidelity: float = 0.99,
                decoherence_rate: float = 0.2,
                p_gen: float = 0.8,
                p_swap: float = 0.8,
                send_rate: Optional[int] = None,
                lifetime: float = 12):
        super().__init__()
        self.init_fidelity = init_fidelity
        self.decoherence_rate = decoherence_rate
        self.p_gen = p_gen
        self.p_swap = p_swap
        self.gen_rate = send_rate
        self.lifetime = lifetime
        self.net: QuantumNetwork = None
        self.own: QNode = None
        self.memory: QuantumMemory = None
        self.adjacent: Dict[str, QuantumChannel] = {}
        self.success = []
        self.send_count = 0
        self.is_center = False
    
    def install(self, node: QNode, simulator: Simulator):
        super().install(node, simulator)
        self.simulator: Simulator = simulator
        if isinstance(self._node, QNode):
            self.own: QNode = self._node
        else:
            raise TypeError("self._node is not of type QNode")
        if isinstance(self.own.network, QuantumNetwork):
            self.net = self.own.network
        else:
            raise TypeError("self.own.network is not of type QuantumNetwork")
        self.memory: QuantumMemory = self.own.memories[0]
        self.requests = self.net.requests # update fidelity due to send_error

        # get adjecent channels and check if it is center node
        for link in self.own.qchannels:
            if link.node_list[0] == self.own:
                self.adjacent[link.node_list[1].name] = link
            elif link.node_list[1] == self.own:
                self.adjacent[link.node_list[0].name] = link
            else:
                raise Exception("Invalid link")
        
        if len(self.adjacent) > 1:
            self.is_center = True
        
        # set initial event
        if self.is_center:
            # generate entanglement
            self.init_links()
            self.update_links()
    
    def init_links(self):
        for link in self.adjacent.values():
            link.is_entangled = False
            link.init_fidelity = 0
            link.current_fidelity = 0

    # discard entanglement and update fidelity
    def update_links(self):
        # add next event to the next time-slot
        tc = self.simulator.ts
        if self.gen_rate is not None:
            t_time_slot = Time(time_slot=tc.time_slot) + Time(time_slot=1)
            self.simulator.add_event(func_to_event(t_time_slot, self.update_links, by=self))
        
        # check enantanlement lifetime
        for link in self.adjacent.values():
            if link.is_entangled and tc.sec - link.entangled_time.sec > self.lifetime:
                link.is_entangled = False

        # update fidelity
        for link in self.adjacent.values():
            if link.is_entangled:
                t = tc.sec - link.entangled_time.sec
                link.current_fidelity = link.init_fidelity * np.exp(-t / self.lifetime)

    def generate_entanglement(self):
        # add next event to the next time-slot
        tc = self.simulator.ts
        if self.gen_rate is not None:
            t = tc + Time(sec = 1 / self.gen_rate)
            self.simulator.add_event(func_to_event(t, self.update_links, by=self))
        # generate entanglement
        for link in self.adjacent.values():
            if not link.is_entangled:
                if random.random() < self.p_gen:
                    link.is_entangled = True
                    link.init_fidelity = self.init_fidelity * np.exp(-self.decoherence_rate * link.length) # decrease fidelity due to send_error
                    link.current_fidelity = link.init_fidelity
                    link.entangled_time = tc

        
    
        
    
    