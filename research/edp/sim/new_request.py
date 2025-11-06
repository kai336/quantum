# request.py
from qns.network import Request


class NewRequest(Request):
    """
    Request class for protocol which uses swapping tree
    """

    def __init__(self, src, dest, name, priority):
        super().__init__(src, dest)
        self.name = name
        self.priority = priority
        self.swap_plan = None  # swapping tree
        self.swap_progress = None  # the progress of the tree
        self.reserve_links = []

    def __repr__(self):
        return f"NewRequest({self.src}, {self.dest}, {self.name}, {self.priority}, {self.attr})"
