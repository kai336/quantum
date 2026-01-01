# 実験設定

- 実験名: psw_boundary_tmem_095_fine_0p5_0p7
- 作成日: 2025-12-26 

## 必須パラメータ
| 項目 | 値 |
| --- | --- |
| nodes | 50 |
| requests | 5 |
| sim_time | 300000 |
| f_req | 0.8 |
| init_fidelity | 0.95 |
| sweep.t_mem | 0.5, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.6, 0.61, 0.62, 0.63, 0.64, 0.65, 0.66, 0.67, 0.68, 0.69, 0.7 |
| sweep.p_swap | 0.2 |
| sweep.link_fidelity | 0.95 |
| sweep.psw_threshold | 0.94 |
| seeds | 0 |
| runs_per_seed | 1 |

## その他パラメータ
| 項目 | 値 |
| --- | --- |
| exp_name | psw_boundary_tmem_095_fine_0p5_0p7 |
| experiment | psw_boundary |
| description | T_MEM高精度スイープ（t_mem=0.50-0.70 step=0.01, nodes=50, requests=5, init_fidelity=0.95, psw_threshold=0.94, p_swap=0.2固定） |
| gen_rate | 50 |
| memory_capacity | 5 |
| waxman_size | 100000 |
| waxman_alpha | 0.2 |
| waxman_beta | 0.6 |
| sweep | {'t_mem': [0.5, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.6, 0.61, 0.62, 0.63, 0.64, 0.65, 0.66, 0.67, 0.68, 0.69, 0.7], 'p_swap': [0.2], 'link_fidelity': [0.95], 'psw_threshold': [0.94]} |
| verbose_sim | False |
| config_path | configs/psw_boundary_tmem_095_fine_0p5_0p7.yaml |
