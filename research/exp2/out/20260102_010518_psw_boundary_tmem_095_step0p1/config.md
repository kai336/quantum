# 実験設定

- 実験名: psw_boundary_tmem_095_step0p1
- 作成日: 2026-01-02 

## 必須パラメータ
| 項目 | 値 |
| --- | --- |
| nodes | 50 |
| requests | 5 |
| sim_time | 300000 |
| f_req | 0.8 |
| init_fidelity | 0.95 |
| sweep.t_mem | 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 |
| sweep.p_swap | 0.2 |
| sweep.link_fidelity | 0.95 |
| sweep.psw_threshold | 0.94 |
| seeds | 0 |
| runs_per_seed | 1 |

## その他パラメータ
| 項目 | 値 |
| --- | --- |
| exp_name | psw_boundary_tmem_095_step0p1 |
| experiment | psw_boundary |
| description | t_mem 0.1-1.0を0.1刻みでスイープ（nodes=50, requests=5, init_fidelity=0.95, psw_threshold=0.94, p_swap=0.2固定） |
| gen_rate | 50 |
| memory_capacity | 5 |
| waxman_size | 100000 |
| waxman_alpha | 0.2 |
| waxman_beta | 0.6 |
| sweep | {'t_mem': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], 'p_swap': [0.2], 'link_fidelity': [0.95], 'psw_threshold': [0.94]} |
| verbose_sim | False |
| config_path | configs/psw_boundary_tmem_095_step0p1.yaml |
