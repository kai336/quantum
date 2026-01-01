# 実験メモ

- 実験条件（重要パラメータ）:
  - nodes=50 requests=5 sim_time=300000 f_req=0.8
  - t_mem=0.2 p_swap=0.2 link_fidelity=0.95 psw_threshold=0.94

- 観測された境界（PSWが効く/効かない領域）:
  - タイムアウトのため未判定

- 悪化する条件とその兆候:
  - タイムアウト（wallclock 30分）で未判定

- 次に掘るべき範囲:
  - sim_time短縮や条件緩和で完走を優先
