#purification and swapping
from typing import Dict, Optional, List
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

from starttopo import StarTopology
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology.topo import ClassicTopology
# purification and swapping

class PSApp(Application):
    def __init__(self,
                init_fidelity: float = 0.99,
                decoherence_rate: float = 0.2,
                p_gen: float = 0.8,
                p_swap: float = 0.8,
                gen_rate: Optional[int] = None,
                lifetime: float = 12,
                channel_number: int = 2):
        super().__init__()
        self.init_fidelity = init_fidelity
        self.decoherence_rate = decoherence_rate
        self.p_gen = p_gen
        self.p_swap = p_swap
        self.gen_rate = gen_rate
        self.lifetime = lifetime
        self.net: QuantumNetwork = None
        self.own: QNode = None
        self.memory: QuantumMemory = None
        self.adjacent: List[QuantumChannel] = []
        self.success = []
        self.send_count = 0
        self.is_center = False
        self.channel_number = channel_number
    
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
        self.requests = self.net.requests

        # get adjecent channels and check if it is center node
        for link in self.own.qchannels:
            log.debug(f"link: {link.name} {link.node_list[0].name} {link.node_list[1].name}")
            if link.node_list[0] == self.own or link.node_list[1] == self.own:
                self.adjacent.append(link)
            else:
                raise Exception("Invalid link")
        log.debug(f"adjacent: {self.own} {self.adjacent}")
        
        if len(self.adjacent) > self.channel_number:
            self.is_center = True
        
        # set initial event
        if self.is_center:
            # initialize links
            self.init_links()
            # add next event to the next time-slot
            # install() -> generate_entanglement -> update_links(update fidelity and purification) -> swap generate_entanglement -> ...
            ts = self.simulator.ts
            event_generate_entanglement = func_to_event(ts + Time(time_slot=1), self.generate_entanglement, by=self)
            self.simulator.add_event(event_generate_entanglement)
    
    def init_links(self):
        for link in self.adjacent:
            link.is_entangled = False
            link.init_fidelity = self.init_fidelity # mod here for different initial fidelity with diffrent length
            link.current_fidelity = 0
            log.debug(f"init_links: {link.name} {link.is_entangled} {link.init_fidelity} {link.current_fidelity}")

    def generate_entanglement(self):
        # add next event to the next time-slot
        tc = self.simulator.tc
        if self.gen_rate is not None:
            t = tc + Time(sec = 1 / self.gen_rate)
            self.simulator.add_event(func_to_event(t, self.update_links, by=self))
        # generate entanglement
        for link in self.adjacent:
            if not link.is_entangled:
                log.debug(f"generate_attempt: {self.own} {link.name}")
                if random.random() < self.p_gen:
                    link.is_entangled = True
                    #link.init_fidelity = self.init_fidelity * np.exp(-self.decoherence_rate * link.length) # decrease fidelity due to send_error
                    link.current_fidelity = link.init_fidelity
                    link.entangled_time = tc
                    log.debug(f"generate_success: {self.own} {link.name} {link.is_entangled} {format(link.init_fidelity, '.4f')} {format(link.current_fidelity, '.4f')}")

    # discard entanglement and update fidelity
    def update_links(self):
        # add next event to the next time-slot
        tc = self.simulator.tc
        if self.gen_rate is not None:
            t_time_slot = Time(time_slot=tc.time_slot) + Time(time_slot=1)
            self.simulator.add_event(func_to_event(t_time_slot, self.swapping, by=self))
        
        # check enantanlement lifetime
        for link in self.adjacent:
            if link.is_entangled and tc.sec - link.entangled_time.sec > self.lifetime:
                link.is_entangled = False
                log.debug(f"dropped_links: {self.own} {link.name} {link.is_entangled} {format(link.init_fidelity, '.4f')} {format(link.current_fidelity, '.4f')}")

        # update fidelity
        for link in self.adjacent:
            if link.is_entangled:
                log.debug(f"update_fidelity(before): {self.own} {link.name} {link.is_entangled} {format(link.init_fidelity, '.4f')} {format(link.current_fidelity, '.4f')}")
                t = tc.sec - link.entangled_time.sec
                link.current_fidelity = link.init_fidelity * np.exp(-t / self.lifetime)
                log.debug(f"update_fidelity(after): {self.own}  {link.name} {link.is_entangled} {format(link.init_fidelity, '.4f')} {format(link.current_fidelity, '.4f')}")

    def swapping(self):
        # add next event to the next time-slot
        tc = self.simulator.tc
        if self.gen_rate is not None:
            t_time_slot = Time(time_slot=tc.time_slot) + Time(time_slot=1)
            self.simulator.add_event(func_to_event(t_time_slot, self.generate_entanglement, by=self))
        # swapping for request
    
    def swap(self, l1, l2):
        if l1.is_entangled and l2.is_entangled:
            if random.random() < self.p_swap:
                l1.is_entangled = False
                l2.is_entangled = False
                l1.current_fidelity = 0
                l2.current_fidelity = 0
                return True
            else:
                return False
        else:
            return False

    def purify(self, l1, l2):
        fmin = min(l1.current_fidelity, l2.current_fidelity)
        if random.random() > (fmin ** 2 + 5 / 9 * (1 - fmin) ** 2 + 2 / 3 * fmin * (1 - fmin)):
            l1.is_entangled = False
            l1.current_fidelity = 0
            l2.is_entangled = False
            l2.current_fidelity = 0
            return False
        else:
            f = (fmin ** 2 + (1 - fmin) ** 2 / 9) / (fmin ** 2 + 5 / 9 * (1 - fmin) ** 2 + 2 / 3 * fmin * (1 - fmin))
            l1.current_fidelity = f
            l2.current_fidelity = 0
            return True
    
def test_ps():
    s = Simulator(0, 5, accuracy=1)
    log.install(s)
    log.logger.setLevel(log.logging.DEBUG)
    topo = StarTopology(nodes_number=5,
                        channel_number=2,
                        qchannel_args={"length": 1000},
                        memory_args=[{
                            "capacity": 50,
                            "decoherence_rate": 0.2}],
                        nodes_apps=[PSApp(init_fidelity=0.99, gen_rate=1, channel_number=2)])
    
    net = QuantumNetwork(
        topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm())
    net.build_route()

    net.random_requests(number=10, allow_overlay=True)
    net.install(s)
    s.run()

test_ps()