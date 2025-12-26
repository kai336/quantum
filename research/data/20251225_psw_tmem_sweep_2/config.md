# Experiment Config

- name: psw_tmem_sweep
- date: 2025-12-25

## Required Parameters
| name | value |
| --- | --- |
| t_mem | 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0 |
| p_swap | 0.2 |
| psw_threshold | 0.95 |
| init_fidelity | 0.99 |
| requests | 5 |
| nodes | 50 |

## Other Parameters
| name | value |
| --- | --- |
| seeds | 0, 1 |
| runs_per_seed | 2 |
| sim_time | 500000 |
| f_req | 0.8 |
