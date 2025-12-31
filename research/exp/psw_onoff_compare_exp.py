import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXP_DIR = ROOT / "exp"
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

from edp.sim import models
from psw_experiment_utils import summarize_psw_stats, write_csv
from psw_request_waiting_exp import compare_psw_on_off_stats
from run_dir import resolve_run_dir, write_config_md

# ------------------------------------------------------------
# デフォルト設定（必要に応じてCLIで上書き）
# ------------------------------------------------------------
NODES = 50
REQUESTS = 5
SIM_TIME = 1_000_000
F_REQ = 0.8
INIT_FIDELITY = 0.99
P_SWAP = 0.4
PSW_THRESHOLD = 0.9
T_MEM = 1000.0
SEEDS: List[int] = list(range(10))
RUNS_PER_SEED = 5
VERBOSE_SIM = False

OUTPUT_LONG = "psw_onoff_compare_long.csv"
OUTPUT_WIDE = "psw_onoff_compare_wide.csv"
REQUIRED_PARAMS = (
    "t_mem",
    "p_swap",
    "psw_threshold",
    "init_fidelity",
    "requests",
    "nodes",
    "seeds",
    "runs_per_seed",
    "sim_time",
    "f_req",
)


def _parse_seeds(values: Iterable[str]) -> List[int]:
    seeds: List[int] = []
    for v in values:
        if "," in v:
            seeds.extend(int(x) for x in v.split(",") if x)
        else:
            seeds.append(int(v))
    return seeds


def main() -> None:
    logging.shutdown
    parser = argparse.ArgumentParser(description="Compare PSW on/off for one scenario")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument("--t-mem", type=float, default=T_MEM)
    parser.add_argument("--p-swap", type=float, default=P_SWAP)
    parser.add_argument("--init-fidelity", type=float, default=INIT_FIDELITY)
    parser.add_argument("--psw-threshold", type=float, default=PSW_THRESHOLD)
    parser.add_argument("--nodes", type=int, default=NODES)
    parser.add_argument("--requests", type=int, default=REQUESTS)
    parser.add_argument("--sim-time", type=float, default=SIM_TIME)
    parser.add_argument("--f-req", type=float, default=F_REQ)
    parser.add_argument("--runs-per-seed", type=int, default=RUNS_PER_SEED)
    parser.add_argument("--seeds", nargs="*", default=None)
    parser.add_argument("--verbose-sim", action="store_true", default=VERBOSE_SIM)
    args = parser.parse_args()

    seeds = SEEDS if args.seeds is None else _parse_seeds(args.seeds)

    run_dir = resolve_run_dir("psw_onoff_compare", args.run_dir, args.run_date)
    write_config_md(
        run_dir,
        "psw_onoff_compare",
        {
            "t_mem": args.t_mem,
            "p_swap": args.p_swap,
            "psw_threshold": args.psw_threshold,
            "init_fidelity": args.init_fidelity,
            "requests": args.requests,
            "nodes": args.nodes,
            "seeds": seeds,
            "runs_per_seed": args.runs_per_seed,
            "sim_time": args.sim_time,
            "f_req": args.f_req,
        },
        REQUIRED_PARAMS,
    )

    models.T_MEM = args.t_mem
    summaries = compare_psw_on_off_stats(
        seeds=seeds,
        runs_per_seed=args.runs_per_seed,
        nodes=args.nodes,
        requests=args.requests,
        sim_time=args.sim_time,
        f_req=args.f_req,
        p_swap=args.p_swap,
        init_fidelity=args.init_fidelity,
        verbose_sim=args.verbose_sim,
        psw_threshold=args.psw_threshold,
    )

    base_fields = {
        "t_mem": args.t_mem,
        "p_swap": args.p_swap,
        "psw_threshold": args.psw_threshold,
        "init_fidelity": args.init_fidelity,
        "requests": args.requests,
        "nodes": args.nodes,
        "seeds": ",".join(str(s) for s in seeds),
        "runs_per_seed": args.runs_per_seed,
        "sim_time": args.sim_time,
        "f_req": args.f_req,
    }
    long_rows, wide_row = summarize_psw_stats(summaries, base_fields)
    write_csv(run_dir / OUTPUT_LONG, long_rows)
    write_csv(run_dir / OUTPUT_WIDE, [wide_row])
    print(f"Wrote: {run_dir / OUTPUT_LONG}")
    print(f"Wrote: {run_dir / OUTPUT_WIDE}")


if __name__ == "__main__":
    main()
