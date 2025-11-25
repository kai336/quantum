# request.py
from qns.entity.operator.event import QNode
from qns.network import Request


class NewRequest(Request):
    """
    Request class for protocol which uses swapping tree
    """

    def __init__(
        self,
        name: str,
        src: QNode,
        dest: QNode,
        priority,
        f_req: float = 0.7,
        is_done: bool = False,
    ):
        super().__init__(src, dest)
        self.name = name
        self.priority = priority
        self.swap_plan = None  # swapping tree
        self.swap_progress = None  # the progress of the tree
        self.reserve_links = []
        self.f_req = f_req
        self.is_done = is_done

    def __repr__(self):
        return f"NewRequest({self.src}, {self.dest}, {self.name}, {self.priority}, {self.attr})"
