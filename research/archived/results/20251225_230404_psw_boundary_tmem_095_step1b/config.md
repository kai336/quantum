# 実験設定

- 実験名: psw_boundary_tmem_095_step1b
- 作成日: 2025-12-25 

## 必須パラメータ
| 項目 | 値 |
| --- | --- |
| nodes | 50 |
| requests | 5 |
| sim_time | 200000 |
| f_req | 0.8 |
| init_fidelity | 0.95 |
| sweep.t_mem | 0.4, 0.3, 0.2 |
| sweep.p_swap | 0.2 |
| sweep.link_fidelity | 0.95 |
| sweep.psw_threshold | 0.94 |
| seeds | 0 |
| runs_per_seed | 1 |

## その他パラメータ
| 項目 | 値 |
| --- | --- |
| exp_name | psw_boundary_tmem_095_step1b |
| experiment | psw_boundary |
| description | T_MEM短縮ステップ1b（0.4,0.3,0.2） |
| gen_rate | 50 |
| memory_capacity | 5 |
| waxman_size | 100000 |
| waxman_alpha | 0.2 |
| waxman_beta | 0.6 |
| sweep | {'t_mem': [0.4, 0.3, 0.2], 'p_swap': [0.2], 'link_fidelity': [0.95], 'psw_threshold': [0.94]} |
| verbose_sim | False |
| config_path | /home/kai/quantum/research/exp2/configs/psw_boundary_tmem_095_step1b.yaml |
