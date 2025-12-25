#!/bin/sh
set -eu

uv run ./research/exp/psw_tmem_sweep_exp.py \
  --t-mem 10 --t-mem 1 --t-mem 0.1 --t-mem 0.01 \
  --nodes 50 --requests 5 --init-fidelity 0.99 --psw-threshold 0.95 \
  --runs-per-seed 2
