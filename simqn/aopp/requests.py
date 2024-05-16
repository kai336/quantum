from typing import Dict
from qns.network import Request as OriginalReq

class Request(OriginalReq):
    def __init__(self, src, dest, attr: Dict = {}, canmove: bool=False, pos: int=0, succeed: bool=False) -> None:
        super().__init__(src, dest, attr)

        self.canmove = canmove
        self.pos = pos
        self.succeed = succeed