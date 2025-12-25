import argparse
import concurrent.futures as futures
import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXP_DIR = ROOT / "exp"
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

from edp.sim import models

from psw_experiment_utils import summarize_psw_stats
from psw_request_waiting_exp import PSWStatsSummary, compare_psw_on_off_stats
from run_dir import resolve_run_dir, write_config_md

# ------------------------------------------------------------
# T_MEMスイープ（固定: nodes=50, requests=5, init_fidelity=0.9, threshold=0.895）
# ------------------------------------------------------------
NODES = 50
REQUESTS = 5
SIM_TIME = 500_000
F_REQ = 0.8
INIT_FIDELITY = 0.9
SEEDS = [0, 1]
RUNS_PER_SEED = 2
VERBOSE_SIM = False
LOG_LEVEL = "INFO"

P_SWAP = 0.2
PSW_THRESHOLD = 0.895

# T_MEM範囲: 0.01–10（等間隔5点）
T_MEM_VALUES = [0.01, 2.5, 5.0, 7.5, 10.0]

OUTPUT_LONG_NAME = "psw_tmem_sweep_custom_long.csv"
OUTPUT_WIDE_NAME = "psw_tmem_sweep_custom_wide.csv"
REQUIRED_PARAMS = ("t_mem", "p_swap", "psw_threshold", "init_fidelity", "requests", "nodes")


@dataclass(frozen=True)
class Scenario:
    t_mem: float
    psw_threshold: float
    p_swap: float


def iter_scenarios(
    *,
    t_mem_values: Iterable[float],
    psw_threshold: float,
    p_swap: float,
) -> Iterable[Scenario]:
    for t_mem in t_mem_values:
        yield Scenario(t_mem=float(t_mem), psw_threshold=psw_threshold, p_swap=p_swap)


def summarize_to_rows(
    scenario: Scenario, summaries: list[PSWStatsSummary]
) -> tuple[list[dict], dict]:
    base_fields = {
        "t_mem": scenario.t_mem,
        "psw_threshold": scenario.psw_threshold,
        "p_swap": scenario.p_swap,
    }
    return summarize_psw_stats(summaries, base_fields)


def run_scenario(
    *,
    t_mem: float,
    psw_threshold: float,
    p_swap: float,
    seeds: Iterable[int],
    runs_per_seed: int,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    init_fidelity: float,
    verbose_sim: bool,
) -> tuple[list[dict], dict]:
    """1つのT_MEMシナリオを実行し、CSV用の行を返す。"""
    scenario = Scenario(t_mem=t_mem, psw_threshold=psw_threshold, p_swap=p_swap)
    models.T_MEM = t_mem
    summaries = compare_psw_on_off_stats(
        seeds=seeds,
        runs_per_seed=runs_per_seed,
        nodes=nodes,
        requests=requests,
        sim_time=sim_time,
        f_req=f_req,
        p_swap=p_swap,
        init_fidelity=init_fidelity,
        verbose_sim=verbose_sim,
        psw_threshold=psw_threshold,
    )
    return summarize_to_rows(scenario, summaries)


def main() -> None:
    logging.shutdown
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))

    parser = argparse.ArgumentParser(
        description="Sweep T_MEM with custom defaults for PSW experiments"
    )
    parser.add_argument(
        "--t-mem",
        dest="t_mem_values",
        type=float,
        action="append",
        default=None,
        help="Memory lifetime T_MEM in seconds (repeatable). Default: built-in list.",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="Comma-separated seeds (e.g. 0,1). Default: built-in list.",
    )
    parser.add_argument(
        "--runs-per-seed",
        type=int,
        default=None,
        help="Runs per seed. Default: built-in value.",
    )
    parser.add_argument(
        "--sim-time",
        type=float,
        default=None,
        help="Simulation time (timeslots). Default: built-in value.",
    )
    parser.add_argument(
        "--nodes",
        type=int,
        default=None,
        help="Number of nodes. Default: built-in value.",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=None,
        help="Number of requests. Default: built-in value.",
    )
    parser.add_argument(
        "--init-fidelity",
        type=float,
        default=None,
        help="Initial fidelity of link EP. Default: built-in value.",
    )
    parser.add_argument(
        "--psw-threshold",
        type=float,
        default=None,
        help="PSW threshold. Default: built-in value.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Output directory for this run. Default: data/YYYYMMDD_psw_tmem_sweep_custom",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=None,
        help="Run date tag (YYYYMMDD). Default: today.",
    )
    parser.add_argument(
        "--output-long",
        type=Path,
        default=None,
        help="Output CSV (long format)",
    )
    parser.add_argument(
        "--output-wide",
        type=Path,
        default=None,
        help="Output CSV (wide format)",
    )
    parser.add_argument(
        "--scenario-timeout-sec",
        type=float,
        default=900.0,
        help="Timeout (sec) per T_MEM scenario. Default: 900 sec (15 min).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing CSVs instead of overwriting them.",
    )
    args = parser.parse_args()

    t_mem_values = T_MEM_VALUES if args.t_mem_values is None else args.t_mem_values
    seeds = SEEDS if args.seeds is None else [int(x) for x in args.seeds.split(",") if x]
    runs_per_seed = RUNS_PER_SEED if args.runs_per_seed is None else args.runs_per_seed
    sim_time = SIM_TIME if args.sim_time is None else args.sim_time
    init_fidelity = INIT_FIDELITY if args.init_fidelity is None else args.init_fidelity
    psw_threshold = PSW_THRESHOLD if args.psw_threshold is None else args.psw_threshold
    nodes = NODES if args.nodes is None else args.nodes
    requests = REQUESTS if args.requests is None else args.requests

    run_dir = resolve_run_dir("psw_tmem_sweep_custom", args.run_dir, args.run_date)
    out_long: Path = args.output_long or (run_dir / OUTPUT_LONG_NAME)
    out_wide: Path = args.output_wide or (run_dir / OUTPUT_WIDE_NAME)
    out_long.parent.mkdir(parents=True, exist_ok=True)
    out_wide.parent.mkdir(parents=True, exist_ok=True)
    if not args.append:
        out_long.unlink(missing_ok=True)
        out_wide.unlink(missing_ok=True)

    write_config_md(
        run_dir,
        "psw_tmem_sweep_custom",
        {
            "t_mem": t_mem_values,
            "p_swap": P_SWAP,
            "psw_threshold": psw_threshold,
            "init_fidelity": init_fidelity,
            "requests": requests,
            "nodes": nodes,
            "seeds": seeds,
            "runs_per_seed": runs_per_seed,
            "sim_time": sim_time,
            "f_req": F_REQ,
        },
        REQUIRED_PARAMS,
    )

    long_header_written = out_long.exists()
    wide_header_written = out_wide.exists()

    for scenario in iter_scenarios(
        t_mem_values=t_mem_values, psw_threshold=psw_threshold, p_swap=P_SWAP
    ):
        with futures.ProcessPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(
                run_scenario,
                t_mem=scenario.t_mem,
                psw_threshold=scenario.psw_threshold,
                p_swap=scenario.p_swap,
                seeds=seeds,
                runs_per_seed=runs_per_seed,
                nodes=nodes,
                requests=requests,
                sim_time=sim_time,
                f_req=F_REQ,
                init_fidelity=init_fidelity,
                verbose_sim=VERBOSE_SIM,
            )
            try:
                long_rows, wide_row = fut.result(timeout=args.scenario_timeout_sec)
            except futures.TimeoutError:
                fut.cancel()
                ex.shutdown(cancel_futures=True)
                print(
                    f"[timeout] t_mem={scenario.t_mem:g} exceeded "
                    f"{args.scenario_timeout_sec} sec; skipping."
                )
                continue

        if long_rows:
            if not long_header_written:
                with out_long.open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(long_rows[0].keys()))
                    w.writeheader()
                    w.writerows(long_rows)
                long_header_written = True
            else:
                with out_long.open("a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(long_rows[0].keys()))
                    w.writerows(long_rows)

        if not wide_header_written:
            with out_wide.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(wide_row.keys()))
                w.writeheader()
                w.writerow(wide_row)
            wide_header_written = True
        else:
            with out_wide.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(wide_row.keys()))
                w.writerow(wide_row)

        off_avg = next((row for row in long_rows if row["mode"] == "psw_off"), None)
        on_avg = next((row for row in long_rows if row["mode"] == "psw_on"), None)
        print(
            f"t_mem={scenario.t_mem:g} "
            f"off(avg={off_avg['avg_wait_per_request_slot']}, fin={off_avg['total_finished']}) "
            f"on(avg={on_avg['avg_wait_per_request_slot']}, fin={on_avg['total_finished']}, "
            f"psw_attempts={on_avg['psw_purify_attempts']}, cancelled={on_avg['psw_cancelled']})"
        )

    print(f"Wrote: {out_long}")
    print(f"Wrote: {out_wide}")


if __name__ == "__main__":
    main()
