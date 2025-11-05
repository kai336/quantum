# edp.py
# EDP algorithm

"""
!!!!!!!!!!!!!!!!!!!!!!!!!!TODO!!!!!!!!!!!!!!!!!!!!!!!!!!
x, yのQNode入力に対応させる
!!!!!!!!!!!!!!!!!!!!!!!!!!TODO!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

from qns.entity.qchannel import QuantumChannel
from qns.network import QuantumNetwork
from typing import Dict, Tuple, List
import math

from research.edp.sim.models import f_pur, f_swap, l_pur, l_swap, p_pur

# ネットワーク定義（例）
fidelity = 0.9

# ここをqns仕様にする


def qnet2DictConverter(
    qcs: List[QuantumChannel], gen_rate: int
) -> Dict[Tuple[str, str], Dict[str, float]]:
    qc_dict: Dict[...] = {}
    for qc in qcs:
        src = qc.src
        dest = qc.dest
        fid = qc.fidelity
        qc_dict[(src, dest)] = {"rate": gen_rate, "fid": fid}
    return qc_dict


Q = {
    ("A", "B"): {"rate": 10, "fid": fidelity},
    ("B", "C"): {"rate": 10, "fid": fidelity},
    ("C", "D"): {"rate": 10, "fid": fidelity},
    ("D", "E"): {"rate": 10, "fid": fidelity},
    ("E", "F"): {"rate": 10, "fid": fidelity},
}

# フィデリティの候補集合
F = [round(0.70 + 0.01 * i, 3) for i in range(31)]

memo = {}


def batch_EDP(qnet: QuantumNetwork):
    reqs = qnet.requests
    results = []
    for req in reqs:
        res = EDP(req)
        results.append(res)

    return results


def EDP(x, y, f_req, depth=0, max_depth=20):
    # indent = '  ' * depth
    key = (x, y, f_req)

    if depth > max_depth:
        return None

    if key in memo:
        return memo[key]

    best_latency = math.inf
    best_tree = None

    # 直接リンク
    if (x, y) in Q and Q[(x, y)]["fid"] >= f_req:
        latency = 1 / Q[(x, y)]["rate"]
        best_latency = latency
        best_tree = {"type": "Link", "link": (x, y)}

    if (y, x) in Q and Q[(y, x)]["fid"] >= f_req:
        latency = 1 / Q[(y, x)]["rate"]
        if latency < best_latency:
            best_latency = latency
            best_tree = {"type": "Link", "link": (y, x)}

    # Swap
    path = ["A", "B", "C", "D", "E", "F"]
    i_x = path.index(x)
    i_y = path.index(y)
    if i_x > i_y:
        i_x, i_y = i_y, i_x
    valid_z = path[i_x + 1 : i_y]

    for z in valid_z:
        for f1 in F:
            for f2 in F:
                f_sw = f_swap(f1, f2)
                if f_sw >= f_req:
                    res1 = EDP(x, z, f1, depth + 1, max_depth)
                    res2 = EDP(z, y, f2, depth + 1, max_depth)
                    if res1 and res2:
                        latency = l_swap(res1[0], res2[0])
                        if latency < best_latency:
                            best_latency = latency
                            best_tree = {
                                "type": "Swap",
                                "via": z,
                                "x": x,
                                "y": y,
                                "left": res1[1],
                                "right": res2[1],
                            }

    # Purify
    for f0 in F:
        if f0 >= f_req:
            continue
        f_pur = f_pur(f0, f0)
        if f_pur >= f_req:
            res = EDP(x, y, f0, depth + 1, max_depth)
            if res:
                latency = l_pur(res[0], f0)
                if latency < best_latency:
                    best_latency = latency
                    best_tree = {"type": "Purify", "x": x, "y": y, "child": res[1]}

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

# 実行例
result = EDP("A", "E", 0.8)
if result:
    latency, tree = result
    print(f"latency: {latency}")
    print("tree:", tree)
    print_tree(tree)
else:
    print("適切な構造が見つかりませんでした。")
