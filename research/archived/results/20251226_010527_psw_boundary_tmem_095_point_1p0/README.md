# 実験メモ

- 実験条件:
  - nodes=50 requests=5 sim_time=300000 f_req=0.8
  - sweep: t_mem=[1.0], p_swap=[0.2], link_fidelity=[0.95], psw_threshold=[0.94]
  - seeds=[0] runs_per_seed=1
- 観測された境界（PSWが効く/効かない領域）:
  - 効く側: まだ明確な差分なし
  - 効かない側: まだ明確な差分なし
- 悪化する条件とその兆候:
  - 現状は明確な悪化兆候なし（要追加スイープ）
- 次に掘るべき範囲:
  - 境界候補(差分が小さい条件)の周辺を細分化: t_mem=1.0, p_swap=0.2, link_fidelity=0.95, psw_threshold=0.94
