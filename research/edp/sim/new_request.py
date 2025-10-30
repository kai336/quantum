# request.py
from qns.network import Request
from typing import Dict

class NewRequest(Request):
    def __init__(self, src, dest,
        name: str,
        priority,
        attr: Dict = ...,
    ) -> None:
        super().__init__(src, dest, attr)
        self.name = name
        self.priority=  priority
        self.swap_plan = None
        self.swap_progress = None
        self.reserve_links = []
    
    def __repr__(self):
        return f"NewRequest({self.src}, {self.dest}, {self.name}, {self.priority}, {self.attr})"
