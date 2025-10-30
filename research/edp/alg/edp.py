# edp.pys
# EDP algorithm
import math

# ネットワーク定義（例）
fidelity = 0.9
Q = {
    ("A", "B"): {"rate": 10, "fid": fidelity},
    ("B", "C"): {"rate": 10, "fid": fidelity},
    ("C", "D"): {"rate": 10, "fid": fidelity},
    ("D", "E"): {"rate": 10, "fid": fidelity},
    ("E", "F"): {"rate": 10, "fid": fidelity},
}

# フィデリティの候補集合
F = [round(0.70 + 0.01 * i, 3) for i in range(31)]


# スワップ後フィデリティの計算
def Fswap(f1, f2):
    return 0.25 * (1 + (1 / 3) * (4 * f1 - 1) * (4 * f2 - 1))


# スワップ後遅延の計算
def Lswap(l1, l2, pf=0.8, tau_f=1, tau_c=1):
    return (1.5 * max(l1, l2) + (tau_f + tau_c)) / pf


# ピュリフィケーション後のフィデリティ（簡易モデル）
def Fpur(ft, fs):
    return (ft * fs + (1 - ft) / 3 * (1 - fs) / 3) / (
        ft * fs
        + ft * (1 - fs) / 3
        + (1 - ft) / 3 * fs
        + 5 * (1 - ft) / 3 * (1 - fs) / 3
    )


# ピュリフィケーションの遅延（簡易モデル）
def Lpur(l, f, pp=0.8, tau_p=10, tau_c=10):
    return (l + tau_p + tau_c) / pp


memo = {}


def DP(x, y, f_req, depth=0, max_depth=20):
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
                f_sw = Fswap(f1, f2)
                if f_sw >= f_req:
                    res1 = DP(x, z, f1, depth + 1, max_depth)
                    res2 = DP(z, y, f2, depth + 1, max_depth)
                    if res1 and res2:
                        latency = Lswap(res1[0], res2[0])
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
        f_pur = Fpur(f0, f0)
        if f_pur >= f_req:
            res = DP(x, y, f0, depth + 1, max_depth)
            if res:
                latency = Lpur(res[0], f0)
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
result = DP("A", "E", 0.8)
if result:
    latency, tree = result
    print(f"latency: {latency}")
    print("tree:", tree)
    print_tree(tree)
else:
    print("適切な構造が見つかりませんでした。")
