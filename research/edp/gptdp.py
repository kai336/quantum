import math

# ネットワーク定義（例）
fidelity = 0.9
Q = {
    ('A', 'B'): {'rate': 10, 'fid': fidelity},
    ('B', 'C'): {'rate': 10, 'fid': fidelity},
    ('C', 'D'): {'rate': 10, 'fid': fidelity},
    ('D', 'E'): {'rate': 10, 'fid': fidelity},
    ('E', 'F'): {'rate': 10, 'fid': fidelity},
}



# フィデリティの候補集合
F = [round(0.70 + 0.01 * i, 3) for i in range(31)]  # 21段階


# スワップ後フィデリティの計算
def Fswap(f1, f2):
    return 0.25 * (1 + (1/3)*(4*f1 -1)*(4*f2 -1))

# スワップ後遅延の計算
def Lswap(l1, l2, pf=0.8, tau_f=1, tau_c=1):
    return (1.5 * max(l1, l2) + (tau_f + tau_c)) / pf

# ピュリフィケーション後のフィデリティ（簡易モデル）
def Fpur(ft, fs):
    return (ft * fs + (1 - ft)/3 * (1 - fs)/3) / (
           ft * fs + ft*(1 - fs)/3 + (1 - ft)/3 * fs + 5*(1 - ft)/3 * (1 - fs)/3)

# ピュリフィケーションの遅延（簡易モデル）
def Lpur(l, f, pp=0.8, tau_p=10, tau_c=10):
    return (l + tau_p + tau_c) / pp

memo = {}

def DP(x, y, f_req, depth=0, max_depth=20):
    indent = '  ' * depth
    key = (x, y, f_req)

    print(f"{indent}DP call: {x}-{y}, f_req={f_req:.3f}, depth={depth}")

    if depth > max_depth:
        print(f"{indent}Exceeded max depth at {x}-{y} f_req={f_req}")
        return None

    if key in memo:
        print(f"{indent}Memo hit: {x}-{y} f_req={f_req}")
        return memo[key]

    best_latency = math.inf
    best_tree = None

    # 直接リンクの場合
    if (x, y) in Q and Q[(x, y)]['fid'] >= f_req:
        latency = 1 / Q[(x, y)]['rate']
        print(f"{indent}Direct link usable {x}-{y} latency={latency}")
        best_latency = latency
        best_tree = f"Link({x}-{y})"

    if (y, x) in Q and Q[(y, x)]['fid'] >= f_req:
        latency = 1 / Q[(y, x)]['rate']
        print(f"{indent}Direct link usable {y}-{x} latency={latency}")
        if latency < best_latency:
            best_latency = latency
            best_tree = f"Link({y}-{x})"

    # swapping
    all_nodes = set()
    for link in Q.keys():
        all_nodes.update(link)

    path = ['A', 'B', 'C', 'D', 'E', 'F']
    i_x = path.index(x)
    i_y = path.index(y)
    if i_x > i_y:
        i_x, i_y = i_y, i_x
    valid_z = path[i_x+1:i_y]  # xとyの間だけ

    for z in valid_z:
        if z == x or z == y:
            continue
        for f1 in F:
            for f2 in F:
                f_sw = Fswap(f1, f2)
                if f_sw >= f_req:
                    print(f"{indent}Try swap via {z} with f1={f1}, f2={f2}, f_sw={f_sw:.3f}")
                    res1 = DP(x, z, f1, depth + 1, max_depth)
                    res2 = DP(z, y, f2, depth + 1, max_depth)
                    if res1 and res2:
                        latency = Lswap(res1[0], res2[0])
                        if latency < best_latency:
                            best_latency = latency
                            best_tree = f"Swap({x}-{y} via {z}): {res1[1]}, {res2[1]}"
    
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
                    best_tree = f"Purify({x}-{y}): {res[1]}"

    if best_latency < math.inf:
        memo[key] = (best_latency, best_tree)
        print(f"{indent}Best found {x}-{y} f_req={f_req:.3f} f_link={fidelity} latency={best_latency}")
        return memo[key]
    else:
        print(f"{indent}No valid path for {x}-{y} f_req={f_req:.3f}")
        memo[key] = None
        return None





# 実行例
result = DP('A', 'E', 0.8)
if result:
    latency, tree = result
    print(f"最適遅延: {latency}")
    print(f"ツリー構造: {tree}")
else:
    print("適切な構造が見つかりませんでした。")
