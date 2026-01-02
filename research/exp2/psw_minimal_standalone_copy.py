"""最小依存でPSW on/offをスイープする単体スクリプト。

- 依存は edp/qns と標準ライブラリのみ（exp2内の他モジュール非依存）。
- パラメタはこのファイル冒頭の定数だけで完結。
- 出力は research/exp2/out/<timestamp>_psw_minimal/ 配下に raw.csv / summary.csv / plots。
"""

from __future__ import annotations

import contextlib
import csv
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edp.app.controller_app import ControllerApp
from edp.app.node_app import NodeApp
from edp.sim import SIMULATOR_ACCURACY, models
from qns.entity.node import QNode
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology import WaxmanTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed

# === パラメタ（ここを書き換えるだけ） ===
EXP_NAME = "t_mem sweep"
T_MEM_VALUES: Sequence[float] = [
    20.0,
    10.0,
    8.0,
    4.0,
    2.0,
    1.0,
    0.8,
    0.4,
]
P_SWAP = 0.4
LINK_FIDELITY = 0.95
PSW_THRESHOLD = 0.94
NODES = 50
REQUESTS = 5
SIM_TIME = 60  # seconds
F_REQ = 0.8
SEEDS: Sequence[int] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
RUNS_PER_SEED = 10
GEN_RATE = 50
MEMORY_CAPACITY = 5
WAXMAN_SIZE = 100000
WAXMAN_ALPHA = 0.2
WAXMAN_BETA = 0.6
VERBOSE_SIM = False


# === ユーティリティ ===
def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _create_run_dir() -> Path:
    base = Path(__file__).resolve().parent / "out"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{_timestamp()}_{EXP_NAME}"
    path.mkdir(parents=True, exist_ok=False)
    (path / "plots").mkdir(parents=True, exist_ok=True)
    return path


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if percentile <= 0:
        return xs[0]
    if percentile >= 100:
        return xs[-1]
    k = (len(xs) - 1) * (percentile / 100)
    f = int(k)
    c = f + 1
    if c >= len(xs):
        return xs[-1]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def _safe_div(numer: float, denom: float) -> float | None:
    if denom == 0:
        return None
    return numer / denom


# === シミュレーション本体 ===
def _run_single(
    *,
    t_mem: float,
    p_swap: float,
    link_fidelity: float,
    psw_threshold: float,
    seed: int,
    enable_psw: bool,
) -> Dict[str, Any]:
    s = Simulator(0, SIM_TIME, SIMULATOR_ACCURACY)
    set_seed(seed)
    models.T_MEM = float(t_mem)

    topo = WaxmanTopology(
        nodes_number=NODES,
        size=WAXMAN_SIZE,
        alpha=WAXMAN_ALPHA,
        beta=WAXMAN_BETA,
        nodes_apps=[
            NodeApp(
                p_swap=p_swap,
                gen_rate=GEN_RATE,
                memory_capacity=MEMORY_CAPACITY,
            )
        ],
    )
    net = QuantumNetwork(
        topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm()
    )
    net.build_route()
    net.random_requests(number=REQUESTS)
    # リクエスト生成に使ったrandomシードが、この後のswap成功判定などに影響しないよう再シード
    random.seed()

    controller_node = QNode(
        name="controller",
        apps=[
            ControllerApp(
                p_swap=p_swap,
                f_req=F_REQ,
                gen_rate=GEN_RATE,
                t_mem=t_mem,
                init_fidelity=link_fidelity,
                enable_psw=enable_psw,
                psw_threshold=psw_threshold,
            )
        ],
    )
    net.add_node(controller_node)

    net.install(s)
    net.build_route()
    if net.requests:
        net.query_route(net.requests[0].src, net.requests[0].dest)

    if VERBOSE_SIM:
        s.run()
    else:
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            s.run()

    controller_app = controller_node.apps[0]
    completed = list(controller_app.completed_requests)
    wait_times = [r["finish_time"] for r in completed]
    fidelities = [r["fidelity"] for r in completed]
    sim_span_slot = float(getattr(getattr(s, "te", None), "time_slot", SIM_TIME))

    return {
        "finished": len(completed),
        "wait_times": wait_times,
        "fidelities": fidelities,
        "swap_wait_times": list(getattr(controller_app, "swap_wait_times", [])),
        "psw_attempts": int(getattr(controller_app, "psw_purify_scheduled", 0))
        if enable_psw
        else 0,
        "psw_success": int(getattr(controller_app, "psw_purify_success", 0))
        if enable_psw
        else 0,
        "psw_fail": int(getattr(controller_app, "psw_purify_fail", 0))
        if enable_psw
        else 0,
        "psw_cancelled": int(getattr(controller_app, "psw_cancelled", 0))
        if enable_psw
        else 0,
        "sim_span_slot": sim_span_slot,
        "completed_requests": completed,
    }


def _summarize(row: Mapping[str, Any]) -> Dict[str, Any]:
    wait = list(row["wait_times"])
    fid = list(row["fidelities"])
    swap_wait = list(row["swap_wait_times"])
    finished = int(row["finished"])
    sim_span = float(row["sim_span_slot"])

    return {
        "finished": finished,
        "avg_wait": mean(wait) if wait else None,
        "p50_wait": _percentile(wait, 50),
        "p90_wait": _percentile(wait, 90),
        "throughput": _safe_div(finished, sim_span) if sim_span > 0 else None,
        "final_fidelity_mean": mean(fid) if fid else None,
        "swap_wait_time_mean": mean(swap_wait) if swap_wait else None,
        "psw_attempts": row["psw_attempts"],
        "psw_success": row["psw_success"],
        "psw_fail": row["psw_fail"],
        "psw_cancelled": row["psw_cancelled"],
    }


def _write_csv(
    path: Path, headers: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {h: ("" if row.get(h) is None else row.get(h)) for h in headers}
            )


def _plot_avg_wait(out_png: Path, summary_rows: List[Dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    by_t: Dict[Tuple[float, bool], List[float]] = {}
    for row in summary_rows:
        if row.get("avg_wait") is None:
            continue
        key = (row["t_mem"], row["enable_psw"])
        by_t.setdefault(key, []).append(float(row["avg_wait"]))

    t_list = sorted({k[0] for k in by_t})
    ys_on = [
        mean(by_t.get((t, True), [])) if by_t.get((t, True)) else None for t in t_list
    ]
    ys_off = [
        mean(by_t.get((t, False), [])) if by_t.get((t, False)) else None for t in t_list
    ]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(t_list, ys_off, marker="o", label="PSW off")
    ax.plot(t_list, ys_on, marker="o", label="PSW on")
    ax.set_xlabel("t_mem")
    ax.set_ylabel("avg_wait (slots)")
    ax.set_title("PSW on/off avg_wait")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def main() -> int:
    run_dir = _create_run_dir()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(run_dir / "experiment.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.info("開始: exp_name=%s", EXP_NAME)

    summary_rows: List[Dict[str, Any]] = []
    raw_rows: List[Dict[str, Any]] = []

    for t_mem in T_MEM_VALUES:
        for enable_psw in (False, True):
            for seed in SEEDS:
                for run_index in range(RUNS_PER_SEED):
                    logging.info(
                        "シナリオ t_mem=%.3f enable_psw=%s seed=%s run_index=%s",
                        t_mem,
                        enable_psw,
                        seed,
                        run_index,
                    )
                    try:
                        metrics = _run_single(
                            t_mem=float(t_mem),
                            p_swap=P_SWAP,
                            link_fidelity=LINK_FIDELITY,
                            psw_threshold=PSW_THRESHOLD,
                            seed=seed,
                            enable_psw=enable_psw,
                        )
                        summary = _summarize(metrics)
                        summary.update(
                            {
                                "exp_name": EXP_NAME,
                                "t_mem": t_mem,
                                "p_swap": P_SWAP,
                                "link_fidelity": LINK_FIDELITY,
                                "psw_threshold": PSW_THRESHOLD,
                                "enable_psw": enable_psw,
                                "seed": seed,
                                "run_index": run_index,
                                "status": "ok",
                                "error_type": None,
                                "error_message": None,
                            }
                        )
                        summary_rows.append(summary)
                        for req in metrics["completed_requests"]:
                            raw_rows.append(
                                {
                                    "t_mem": t_mem,
                                    "p_swap": P_SWAP,
                                    "link_fidelity": LINK_FIDELITY,
                                    "psw_threshold": PSW_THRESHOLD,
                                    "enable_psw": enable_psw,
                                    "seed": seed,
                                    "run_index": run_index,
                                    "request_index": req.get("index"),
                                    "request_name": req.get("name"),
                                    "finish_time": req.get("finish_time"),
                                    "fidelity": req.get("fidelity"),
                                }
                            )
                    except Exception as exc:  # noqa: BLE001
                        logging.exception(
                            "シナリオ失敗 t_mem=%s enable_psw=%s", t_mem, enable_psw
                        )
                        summary_rows.append(
                            {
                                "exp_name": EXP_NAME,
                                "t_mem": t_mem,
                                "p_swap": P_SWAP,
                                "link_fidelity": LINK_FIDELITY,
                                "psw_threshold": PSW_THRESHOLD,
                                "enable_psw": enable_psw,
                                "seed": seed,
                                "run_index": run_index,
                                "status": "error",
                                "error_type": type(exc).__name__,
                                "error_message": str(exc),
                            }
                        )

    # CSV出力
    summary_headers = [
        "exp_name",
        "t_mem",
        "p_swap",
        "link_fidelity",
        "psw_threshold",
        "enable_psw",
        "seed",
        "run_index",
        "finished",
        "avg_wait",
        "p50_wait",
        "p90_wait",
        "throughput",
        "final_fidelity_mean",
        "swap_wait_time_mean",
        "psw_attempts",
        "psw_success",
        "psw_fail",
        "psw_cancelled",
        "status",
        "error_type",
        "error_message",
    ]
    raw_headers = [
        "t_mem",
        "p_swap",
        "link_fidelity",
        "psw_threshold",
        "enable_psw",
        "seed",
        "run_index",
        "request_index",
        "request_name",
        "finish_time",
        "fidelity",
    ]
    _write_csv(run_dir / "summary.csv", summary_headers, summary_rows)
    _write_csv(run_dir / "raw.csv", raw_headers, raw_rows)

    # プロット
    try:
        _plot_avg_wait(run_dir / "plots" / "avg_wait_onoff.png", summary_rows)
    except Exception:
        logging.exception("プロット生成に失敗しました")
        (run_dir / "plots" / "placeholder.txt").write_text(
            "プロット生成に失敗しました。\n", encoding="utf-8"
        )

    logging.info("完了 run_dir=%s", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
