import csv
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

from psw_request_waiting_exp import PSWStatsSummary, compare_psw_on_off_stats

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

OUTPUT_LONG_CSV = ROOT / "data" / "psw_threshold_sweep_long.csv"
OUTPUT_WIDE_CSV = ROOT / "data" / "psw_threshold_sweep_wide.csv"


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


def _to_float_str(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.6g}"


def write_long_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("no rows to write")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_wide_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("no rows to write")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def summarize_to_rows(
    scenario: Scenario, summaries: list[PSWStatsSummary]
) -> tuple[list[dict], dict]:
    long_rows: list[dict] = []
    wide_row: dict = {
        "t_mem": scenario.t_mem,
        "psw_threshold": scenario.psw_threshold,
        "p_swap": scenario.p_swap,
    }

    for s in summaries:
        mode = "psw_on" if s.enable_psw else "psw_off"
        long_rows.append(
            {
                "t_mem": scenario.t_mem,
                "psw_threshold": scenario.psw_threshold,
                "p_swap": scenario.p_swap,
                "mode": mode,
                "avg_wait_per_request_slot": _to_float_str(s.avg_wait_per_request),
                "total_finished": s.total_finished,
                "trial_count": s.trial_count,
                "psw_purify_attempts": s.psw_purify_attempts,
                "psw_purify_successes": s.psw_purify_successes,
                "psw_purify_fails": s.psw_purify_fails,
                "psw_cancelled": s.psw_cancelled,
                "psw_purify_attempts_per_finished": _to_float_str(
                    s.psw_purify_attempts_per_finished
                ),
            }
        )

        prefix = "on" if s.enable_psw else "off"
        wide_row[f"avg_wait_{prefix}_slot"] = _to_float_str(s.avg_wait_per_request)
        wide_row[f"total_finished_{prefix}"] = s.total_finished
        wide_row[f"trial_count_{prefix}"] = s.trial_count
        wide_row[f"psw_purify_attempts_{prefix}"] = s.psw_purify_attempts
        wide_row[f"psw_purify_successes_{prefix}"] = s.psw_purify_successes
        wide_row[f"psw_purify_fails_{prefix}"] = s.psw_purify_fails
        wide_row[f"psw_cancelled_{prefix}"] = s.psw_cancelled
        wide_row[f"psw_purify_attempts_per_finished_{prefix}"] = _to_float_str(
            s.psw_purify_attempts_per_finished
        )

    avg_off = None
    avg_on = None
    for s in summaries:
        if s.enable_psw:
            avg_on = s.avg_wait_per_request
        else:
            avg_off = s.avg_wait_per_request
    if avg_off is not None and avg_on is not None:
        wide_row["avg_wait_delta_slot"] = _to_float_str(avg_on - avg_off)
        wide_row["avg_wait_ratio_on_over_off"] = _to_float_str(avg_on / avg_off)
    else:
        wide_row["avg_wait_delta_slot"] = ""
        wide_row["avg_wait_ratio_on_over_off"] = ""

    return long_rows, wide_row


def main() -> None:
    logging.shutdown
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))

    models.T_MEM = T_MEM

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

    write_long_csv(OUTPUT_LONG_CSV, all_long_rows)
    write_wide_csv(OUTPUT_WIDE_CSV, all_wide_rows)
    print(f"Wrote: {OUTPUT_LONG_CSV}")
    print(f"Wrote: {OUTPUT_WIDE_CSV}")


if __name__ == "__main__":
    main()
