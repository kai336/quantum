import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

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
# しきい値×p_swapのスイープ（必要に応じてここを書き換え）
# ------------------------------------------------------------
T_MEM = 1000.0
NODES = 30
REQUESTS = 10
SIM_TIME = 500_000
F_REQ = 0.8
INIT_FIDELITY = 0.99
SEEDS = [0, 1]
RUNS_PER_SEED = 2
VERBOSE_SIM = False
LOG_LEVEL = "INFO"

P_SWAP_VALUES = [0.1, 0.2, 0.3]
PSW_THRESHOLDS = [0.9, 0.995]

OUTPUT_LONG_NAME = "psw_threshold_sweep_long.csv"
OUTPUT_WIDE_NAME = "psw_threshold_sweep_wide.csv"
REQUIRED_PARAMS = ("t_mem", "p_swap", "psw_threshold", "init_fidelity", "requests", "nodes")


@dataclass(frozen=True)
class Scenario:
    t_mem: float
    psw_threshold: float
    p_swap: float


def iter_scenarios(
    *,
    t_mem: float,
    psw_thresholds: Iterable[float],
    p_swap_values: Iterable[float],
) -> Iterable[Scenario]:
    for threshold in psw_thresholds:
        for p_swap in p_swap_values:
            yield Scenario(t_mem=t_mem, psw_threshold=threshold, p_swap=p_swap)


def summarize_to_rows(scenario: Scenario, summaries: list) -> tuple[list[dict], dict]:
    base_fields = {
        "t_mem": scenario.t_mem,
        "psw_threshold": scenario.psw_threshold,
        "p_swap": scenario.p_swap,
    }
    return summarize_psw_stats(summaries, base_fields)


def main() -> None:
    logging.shutdown
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))

    models.T_MEM = T_MEM
    parser = argparse.ArgumentParser(
        description="Sweep psw_threshold and p_swap with fixed T_MEM"
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Output directory for this run. Default: data/YYYYMMDD_psw_threshold_sweep",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=None,
        help="Run date tag (YYYYMMDD). Default: today.",
    )
    args = parser.parse_args()

    run_dir = resolve_run_dir("psw_threshold_sweep", args.run_dir, args.run_date)
    out_long = run_dir / OUTPUT_LONG_NAME
    out_wide = run_dir / OUTPUT_WIDE_NAME

    write_config_md(
        run_dir,
        "psw_threshold_sweep",
        {
            "t_mem": T_MEM,
            "p_swap": P_SWAP_VALUES,
            "psw_threshold": PSW_THRESHOLDS,
            "init_fidelity": INIT_FIDELITY,
            "requests": REQUESTS,
            "nodes": NODES,
            "seeds": SEEDS,
            "runs_per_seed": RUNS_PER_SEED,
            "sim_time": SIM_TIME,
            "f_req": F_REQ,
        },
        REQUIRED_PARAMS,
    )

    all_long_rows: list[dict] = []
    all_wide_rows: list[dict] = []
    for scenario in iter_scenarios(
        t_mem=T_MEM,
        psw_thresholds=PSW_THRESHOLDS,
        p_swap_values=P_SWAP_VALUES,
    ):
        summaries = compare_psw_on_off_stats(
            seeds=SEEDS,
            runs_per_seed=RUNS_PER_SEED,
            nodes=NODES,
            requests=REQUESTS,
            sim_time=SIM_TIME,
            f_req=F_REQ,
            p_swap=scenario.p_swap,
            init_fidelity=INIT_FIDELITY,
            verbose_sim=VERBOSE_SIM,
            psw_threshold=scenario.psw_threshold,
        )
        long_rows, wide_row = summarize_to_rows(scenario, summaries)
        all_long_rows.extend(long_rows)
        all_wide_rows.append(wide_row)

        def _fmt(v: Optional[float]) -> str:
            return "" if v is None else f"{v:.2f}"

        off = next(s for s in summaries if not s.enable_psw)
        on = next(s for s in summaries if s.enable_psw)
        print(
            f"p_swap={scenario.p_swap:.2f}, threshold={scenario.psw_threshold:.3f} "
            f"off(avg={_fmt(off.avg_wait_per_request)}, fin={off.total_finished}) "
            f"on(avg={_fmt(on.avg_wait_per_request)}, fin={on.total_finished}, "
            f"psw_attempts={on.psw_purify_attempts}, cancelled={on.psw_cancelled})"
        )

    write_csv(out_long, all_long_rows)
    write_csv(out_wide, all_wide_rows)
    print(f"Wrote: {out_long}")
    print(f"Wrote: {out_wide}")


if __name__ == "__main__":
    main()
