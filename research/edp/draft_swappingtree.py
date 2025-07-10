from typing import Dict, Optional, List
from qns.entity.memory.memory import QuantumMemory
from qns.entity.node.app import Application
from qns.entity.node.node import QNode
from qns.entity.qchannel.qchannel import QuantumChannel
from qns.simulator.event import func_to_event
from qns.simulator.simulator import Simulator
from qns.network import QuantumNetwork
from qns.simulator.ts import Time
import qns.utils.log as log
import random

def treeswap(s:QNode, d:QNode, path: List[QNode]):
    if isAdjacent(s,d):
        generate(s,d)
        return
    else:
        center = int(len(path(s,d))/2)
        node_center = path[center]
        l_path = path[:center]
        r_path = path[center:]
        treeswap(s, node_center, l_path)
        treeswap(node_center, d, r_path)
        swap(s, node_center, d)
        return
    
def isAdjacent(s:QNode, d:QNode) -> bool:
    for n in s.adjacents:
        if n == d:
            return True
    return False

def path(s:QNode, d:QNode) -> list[QNode]:
    # same to get_route_nodes
    pass

def generate(s:QNode, d:QNode):
    # wait until generate entanglement
    if get_qc(s,d).is_entangled():
        return
    
def swap(s:QNode, m:QNode, d:QNode):
