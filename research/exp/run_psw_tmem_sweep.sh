#!/bin/sh
# sample usage

uv run exp/psw_tmem_sweep_exp.py \
  --t-mem 1 --t-mem 2 --t-mem 3 --t-mem 4 --t-mem 5 --t-mem 6 --t-mem 7 --t-mem 8 --t-mem 9 --t-mem 10 \
  --nodes 50 --requests 5 --init-fidelity 0.99 --psw-threshold 0.95 \
  --runs-per-seed 2
