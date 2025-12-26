# 実験設定

- 実験名: psw_boundary
- 作成日: 2025-12-25 

## 必須パラメータ
| 項目 | 値 |
| --- | --- |
| nodes | 20 |
| requests | 2 |
| sim_time | 50000 |
| f_req | 0.8 |
| init_fidelity | 0.99 |
| sweep.t_mem | 1.0, 10.0 |
| sweep.p_swap | 0.2, 0.6 |
| sweep.link_fidelity | 0.95 |
| sweep.psw_threshold | 0.9 |
| seeds | 0 |
| runs_per_seed | 1 |

## その他パラメータ
| 項目 | 値 |
| --- | --- |
| exp_name | psw_boundary |
| experiment | psw_boundary |
| description | PSW境界探索の小規模スイープ |
| gen_rate | 50 |
| memory_capacity | 5 |
| waxman_size | 100000 |
| waxman_alpha | 0.2 |
| waxman_beta | 0.6 |
| sweep | {'t_mem': [1.0, 10.0], 'p_swap': [0.2, 0.6], 'link_fidelity': [0.95], 'psw_threshold': [0.9]} |
| verbose_sim | False |
| config_path | /home/kai/quantum/research/exp2/configs/psw_boundary.yaml |
