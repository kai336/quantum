# 実験設定

- 実験名: psw_boundary_tmem_0p5_custom
- 作成日: 2025-12-31 

## 必須パラメータ
| 項目 | 値 |
| --- | --- |
| nodes | 50 |
| requests | 5 |
| sim_time | 300000 |
| f_req | 0.8 |
| init_fidelity | 0.9 |
| sweep.t_mem | 0.5 |
| sweep.p_swap | 0.2 |
| sweep.link_fidelity | 0.9 |
| sweep.psw_threshold | 0.89 |
| seeds | 0 |
| runs_per_seed | 1 |

## その他パラメータ
| 項目 | 値 |
| --- | --- |
| exp_name | psw_boundary_tmem_0p5_custom |
| experiment | psw_boundary |
| description | T_MEM単点（t_mem=0.5, nodes=50, requests=5, init_fidelity=0.9, psw_threshold=0.89, p_swap=0.2） |
| gen_rate | 50 |
| memory_capacity | 5 |
| waxman_size | 100000 |
| waxman_alpha | 0.2 |
| waxman_beta | 0.6 |
| sweep | {'t_mem': [0.5], 'p_swap': [0.2], 'link_fidelity': [0.9], 'psw_threshold': [0.89]} |
| verbose_sim | False |
| config_path | research/exp2/configs/psw_boundary_tmem_0p5_custom.yaml |
