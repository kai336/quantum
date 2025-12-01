# edp.py
# EDP algorithm

import math
from typing import Dict, List, Tuple

from qns.entity.node import QNode
from qns.entity.qchannel import QuantumChannel
from qns.network import QuantumNetwork

from edp.sim.models import f_pur, f_swap, l_pur, l_swap, p_pur
from edp.sim.new_qchannel import NewQC
from edp.sim.new_request import NewRequest
from edp.sim.op import Operation, build_ops_from_edp_result

# ネットワーク定義（例）
fidelity = 0.9

# ここをqns仕様にする


def qnet2DictConverter(
    qcs: List[NewQC], gen_rate: int
) -> Dict[Tuple[QNode, QNode], Dict[str, float]]:
    qc_dict: Dict = {}
    for qc in qcs:
        src = qc.node_list[0]
        dest = qc.node_list[1]
        # fid = qc.fidelity
        fid = 0.99
        qc_dict[(src, dest)] = {"rate": gen_rate, "fid": fid}
    return qc_dict


"""
Q = {
    ("A", "B"): {"rate": 10, "fid": fidelity},
    ("B", "C"): {"rate": 10, "fid": fidelity},
    ("C", "D"): {"rate": 10, "fid": fidelity},
    ("D", "E"): {"rate": 10, "fid": fidelity},
    ("E", "F"): {"rate": 10, "fid": fidelity},
}
"""

# フィデリティの候補集合
F = [round(0.70 + 0.01 * i, 3) for i in range(31)]

memo = {}


def batch_EDP(
    qnet: QuantumNetwork, reqs: List[NewRequest], qcs: List[NewQC], gen_rate: int = 50
):
    qnet_dist = qnet2DictConverter(qcs=qcs, gen_rate=gen_rate)
    results: List[Tuple[float, dict] | None] = []
    for req in reqs:
        print("req name: ", req.name)
        print(req.src, req.dest)
        paths = qnet.query_route(req.src, req.dest)
        print(paths)
        if not paths:
            print("route not found; skip EDP")
            results.append(None)
            continue

        path = paths[0][2]
        print("path:", path)
        print("f_req: ", req.f_req)
        res = EDP(
            src=req.src, dest=req.dest, qnet=qnet_dist, path=path, f_req=req.f_req
        )
        if res is not None:
            op_list = build_ops_from_edp_result(res)
            results.append(op_list)
        else:
            print("no swapping tree found")
            results.append(None)
    print(results)
    return results


def EDP(
    path: List[QNode],
    src: QNode,
    dest: QNode,
    qnet: Dict[Tuple[QNode, QNode], Dict[str, float]],
    f_req: float = 0.7,
    depth: int = 0,
    max_depth: int = 20,
):
    key = (src, dest, f_req)

    if depth > max_depth:
        return None

    if key in memo:
        return memo[key]

    best_latency = math.inf
    best_tree = None

    # 直接リンク
    if (src, dest) in qnet and qnet[(src, dest)]["fid"] >= f_req:
        latency = 1 / qnet[(src, dest)]["rate"]
        best_latency = latency
        best_tree = {"type": "Link", "link": (src, dest)}

    if (dest, src) in qnet and qnet[(dest, src)]["fid"] >= f_req:
        latency = 1 / qnet[(dest, src)]["rate"]
        if latency < best_latency:
            best_latency = latency
            best_tree = {"type": "Link", "link": (dest, src)}

    # Swap
    # path = ["A", "B", "C", "D", "E", "F"]
    i_x = path.index(src)
    i_y = path.index(dest)
    if i_x > i_y:
        i_x, i_y = i_y, i_x
    valid_z = path[i_x + 1 : i_y]

    for z in valid_z:
        for f1 in F:
            for f2 in F:
                f_sw = f_swap(f1, f2)
                if f_sw >= f_req:
                    res1 = EDP(
                        path=path,
                        src=src,
                        dest=z,
                        f_req=f1,
                        qnet=qnet,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                    res2 = EDP(
                        path=path,
                        src=z,
                        dest=dest,
                        f_req=f2,
                        qnet=qnet,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                    if res1 and res2:
                        latency = l_swap(res1[0], res2[0])
                        if latency < best_latency:
                            best_latency = latency
                            best_tree = {
                                "type": "Swap",
                                "via": z,
                                "x": src,
                                "y": dest,
                                "left": res1[1],
                                "right": res2[1],
                            }

    # Purify
    for f0 in F:
        if f0 >= f_req:
            continue
        f_purify = f_pur(f0, f0)
        if f_purify >= f_req:
            res = EDP(
                path=path,
                src=src,
                dest=dest,
                f_req=f0,
                qnet=qnet,
                depth=depth + 1,
                max_depth=max_depth,
            )
            if res:
                latency = l_pur(res[0], f0)
                if latency < best_latency:
                    best_latency = latency
                    best_tree = {"type": "Purify", "x": src, "y": dest, "child": res[1]}

    if best_latency < math.inf:
        memo[key] = (best_latency, best_tree)
        return memo[key]
    else:
        memo[key] = None
        return None


# ツリーをきれいに表示する関数
def print_tree(tree, indent=""):
    if tree["type"] == "Link":
        print(f"{indent}- Link {tree['link'][0]}-{tree['link'][1]}")
    elif tree["type"] == "Swap":
        print(f"{indent}- Swap {tree['x']}-{tree['y']} via {tree['via']}")
        print_tree(tree["left"], indent + "  ")
        print_tree(tree["right"], indent + "  ")
    elif tree["type"] == "Purify":
        print(f"{indent}- Purify {tree['x']}-{tree['y']}")
        print_tree(tree["child"], indent + "  ")


"""
tree: {'type': 'Swap', 'via': 'C', 'x': 'A', 'y': 'E', 'left': {'type': 'Purify', 'x': 'A', 'y': 'C', 'child': {'type': 'Purify', 'x': 'A', 'y': 'C', 'child': {'type': 'Purify', 'x': 'A', 'y': 'C', 'child': {'type': 'Swap', 'via': 'B', 'x': 'A', 'y': 'C', 'left': {'type': 'Link', 'link': ('A', 'B')}, 'right': {'type': 'Link', 'link': ('B', 'C')}}}}}, 'right': {'type': 'Purify', 'x': 'C', 'y': 'E', 'child': {'type': 'Purify', 'x': 'C', 'y': 'E', 'child': {'type': 'Purify', 'x': 'C', 'y': 'E', 'child': {'type': 'Swap', 'via': 'D', 'x': 'C', 'y': 'E', 'left': {'type': 'Link', 'link': ('C', 'D')}, 'right': {'type': 'Link', 'link': ('D', 'E')}}}}}}
"""

"""
# 実行例
result = EDP("A", "E", 0.8)
if result:
    latency, tree = result
    print(f"latency: {latency}")
    print("tree:", tree)
    print_tree(tree)
else:
    print("適切な構造が見つかりませんでした。")
"""
