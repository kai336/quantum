# 実験設定

- 実験名: psw_boundary_trigger_sync
- 作成日: 2026-01-02 

## 必須パラメータ
| 項目 | 値 |
| --- | --- |
| nodes | 20 |
| requests | 2 |
| sim_time | 300000 |
| f_req | 0.8 |
| init_fidelity | 0.99 |
| sweep.t_mem | 1.0, 10.0 |
| sweep.p_swap | 0.2, 0.6 |
| sweep.link_fidelity | 0.99 |
| sweep.psw_threshold | 0.995 |
| seeds | 0 |
| runs_per_seed | 1 |

## その他パラメータ
| 項目 | 値 |
| --- | --- |
| exp_name | psw_boundary_trigger |
| experiment | psw_boundary |
| description | PSW発動を狙う小規模スイープ |
| gen_rate | 50 |
| memory_capacity | 5 |
| waxman_size | 100000 |
| waxman_alpha | 0.2 |
| waxman_beta | 0.6 |
| sweep | {'t_mem': [1.0, 10.0], 'p_swap': [0.2, 0.6], 'link_fidelity': [0.99], 'psw_threshold': [0.995]} |
| verbose_sim | False |
| config_path | exp2/configs/psw_boundary_trigger.yaml |
