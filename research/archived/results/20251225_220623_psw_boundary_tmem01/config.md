# 実験設定

- 実験名: psw_boundary_tmem01
- 作成日: 2025-12-25 

## 必須パラメータ
| 項目 | 値 |
| --- | --- |
| nodes | 10 |
| requests | 2 |
| sim_time | 10000 |
| f_req | 0.8 |
| init_fidelity | 0.99 |
| sweep.t_mem | 0.1 |
| sweep.p_swap | 0.2 |
| sweep.link_fidelity | 0.99 |
| sweep.psw_threshold | 0.995 |
| seeds | 0 |
| runs_per_seed | 1 |

## その他パラメータ
| 項目 | 値 |
| --- | --- |
| exp_name | psw_boundary_tmem01 |
| experiment | psw_boundary |
| description | T_MEMを短縮した単点テスト |
| gen_rate | 50 |
| memory_capacity | 5 |
| waxman_size | 100000 |
| waxman_alpha | 0.2 |
| waxman_beta | 0.6 |
| sweep | {'t_mem': [0.1], 'p_swap': [0.2], 'link_fidelity': [0.99], 'psw_threshold': [0.995]} |
| verbose_sim | False |
| config_path | /home/kai/quantum/research/exp2/configs/psw_boundary_tmem01.yaml |
