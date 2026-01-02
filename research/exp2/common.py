"""exp2の共通処理（実行・集計・出力・プロット）。"""

from __future__ import annotations

import argparse
import contextlib
import csv
import logging
import math
import os
import sys
import traceback
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edp.app.controller_app import ControllerApp
from edp.app.node_app import NodeApp
from edp.sim import SIMULATOR_ACCURACY
from edp.sim import models
from qns.entity.node import QNode
from qns.network import QuantumNetwork
from qns.network.route.dijkstra import DijkstraRouteAlgorithm
from qns.network.topology import WaxmanTopology
from qns.network.topology.topo import ClassicTopology
from qns.simulator.simulator import Simulator
from qns.utils.rnd import set_seed

from .schema import DELTA_TARGETS, raw_fieldnames, summary_fieldnames


@dataclass(frozen=True)
class Scenario:
    t_mem: float
    p_swap: float
    link_fidelity: float
    psw_threshold: float


@dataclass(frozen=True)
class RunMetrics:
    finished: int
    wait_times: List[float]
    final_fidelities: List[float]
    swap_wait_times: List[int]
    swap_wait_times_by_req: Dict[str, List[int]]
    psw_attempts: int
    psw_success: int
    psw_fail: int
    psw_cancelled: int
    sim_span_slot: float
    completed_requests: List[Dict[str, Any]]


REQUIRED_CONFIG_KEYS: List[str] = [
    "nodes",
    "requests",
    "sim_time",
    "f_req",
    "init_fidelity",
    "sweep.t_mem",
    "sweep.p_swap",
    "sweep.link_fidelity",
    "sweep.psw_threshold",
    "seeds",
    "runs_per_seed",
]


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """共通CLI引数を追加する。"""
    parser.add_argument("--config", required=True, help="設定YAMLのパス")
    parser.add_argument("--run-dir", default=None, help="結果出力先(省略で自動作成)")
    parser.add_argument("--exp-name", default=None, help="実験名の上書き")
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="plots出力をスキップする",
    )


def setup_logging(run_dir: Path) -> None:
    """ログ出力を初期化する。"""
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "experiment.log"
    handlers = [
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
    try:
        import qns.utils.log as qlog

        qlog.logger.handlers.clear()
        for handler in handlers:
            qlog.logger.addHandler(handler)
        qlog.logger.setLevel(logging.INFO)
    except Exception:
        pass


def load_yaml(path: str | Path) -> Dict[str, Any]:
    """YAML設定を読み込む。"""
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("設定YAMLの最上位はdictである必要があります")
    return data


def _percentile(values: Sequence[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    if percentile <= 0:
        return min(values)
    if percentile >= 100:
        return max(values)
    xs = sorted(values)
    k = (len(xs) - 1) * (percentile / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[int(k)]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def _mean_or_none(values: Sequence[float | int]) -> Optional[float]:
    if not values:
        return None
    return float(mean(values))


def _safe_div(numer: float, denom: float) -> Optional[float]:
    if denom == 0:
        return None
    return numer / denom


def _scenario_id(scenario: Scenario) -> str:
    return (
        f"t_mem={scenario.t_mem}_p_swap={scenario.p_swap}_"
        f"link_fidelity={scenario.link_fidelity}_psw_threshold={scenario.psw_threshold}"
    )


def _run_single(
    *,
    nodes: int,
    requests: int,
    seed: int,
    sim_time: float,
    f_req: float,
    p_swap: float,
    init_fidelity: float,
    enable_psw: bool,
    psw_threshold: Optional[float],
    gen_rate: int,
    memory_capacity: int,
    waxman_size: float,
    waxman_alpha: float,
    waxman_beta: float,
    verbose_sim: bool,
) -> RunMetrics:
    """単発シミュレーションを実行する。"""
    s = Simulator(0, sim_time, SIMULATOR_ACCURACY)
    set_seed(seed)

    topo = WaxmanTopology(
        nodes_number=nodes,
        size=waxman_size,
        alpha=waxman_alpha,
        beta=waxman_beta,
        nodes_apps=[
            NodeApp(
                p_swap=p_swap,
                gen_rate=gen_rate,
                memory_capacity=memory_capacity,
            )
        ],
    )
    net = QuantumNetwork(
        topo=topo, classic_topo=ClassicTopology.All, route=DijkstraRouteAlgorithm()
    )

    net.build_route()
    net.random_requests(number=requests)
    # リクエスト生成のためにset_seedで固定したrandom状態が、この後のswap成功判定まで貫通しないように再シードする
    random.seed()

    controller_node = QNode(
        name="controller",
        apps=[
            ControllerApp(
                p_swap=p_swap,
                f_req=f_req,
                gen_rate=gen_rate,
                init_fidelity=init_fidelity,
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

    if verbose_sim:
        s.run()
    else:
        with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
            s.run()

    controller_app = controller_node.apps[0]
    completed = list(controller_app.completed_requests)
    finished = len(completed)
    wait_times = [r["finish_time"] for r in completed]
    fidelities = [r["fidelity"] for r in completed]

    sim_span_slot = 0.0
    te = getattr(s, "te", None)
    if te is not None and getattr(te, "time_slot", None) is not None:
        sim_span_slot = float(te.time_slot)
    else:
        tc = getattr(s, "tc", None)
        if tc is not None and getattr(tc, "time_slot", None) is not None:
            sim_span_slot = float(tc.time_slot)
        else:
            sim_span_slot = float(sim_time)

    return RunMetrics(
        finished=finished,
        wait_times=wait_times,
        final_fidelities=fidelities,
        swap_wait_times=list(getattr(controller_app, "swap_wait_times", [])),
        swap_wait_times_by_req=dict(
            getattr(controller_app, "swap_wait_times_by_req", {})
        ),
        psw_attempts=int(getattr(controller_app, "psw_purify_scheduled", 0))
        if enable_psw
        else 0,
        psw_success=int(getattr(controller_app, "psw_purify_success", 0))
        if enable_psw
        else 0,
        psw_fail=int(getattr(controller_app, "psw_purify_fail", 0))
        if enable_psw
        else 0,
        psw_cancelled=int(getattr(controller_app, "psw_cancelled", 0))
        if enable_psw
        else 0,
        sim_span_slot=sim_span_slot,
        completed_requests=completed,
    )


def _build_raw_rows(
    *,
    metrics: RunMetrics,
    scenario: Scenario,
    exp_name: str,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    enable_psw: bool,
    seed: int,
    run_index: int,
    status: str,
    error_type: Optional[str],
    error_message: Optional[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    finished_by_index: Dict[int, Dict[str, Any]] = {
        int(item["index"]): item for item in metrics.completed_requests
    }
    wait_by_req = metrics.swap_wait_times_by_req
    for req_id in range(requests):
        item = finished_by_index.get(req_id)
        req_name = item.get("name") if item else f"req{req_id}"
        waits = wait_by_req.get(req_name, [])
        rows.append(
            {
                "exp_name": exp_name,
                "scenario_id": _scenario_id(scenario),
                "nodes": nodes,
                "requests": requests,
                "sim_time": sim_time,
                "f_req": f_req,
                "t_mem": scenario.t_mem,
                "p_swap": scenario.p_swap,
                "link_fidelity": scenario.link_fidelity,
                "psw_threshold": scenario.psw_threshold,
                "enable_psw": enable_psw,
                "seed": seed,
                "run_index": run_index,
                "request_id": req_id,
                "request_name": req_name,
                "finished": 1 if item else 0,
                "finish_time": item.get("finish_time") if item else None,
                "final_fidelity": item.get("fidelity") if item else None,
                "swap_wait_time_mean": _mean_or_none(waits),
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
            }
        )
    return rows


def _build_error_raw_row(
    *,
    scenario: Scenario,
    exp_name: str,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    enable_psw: bool,
    seed: int,
    run_index: int,
    error_type: str,
    error_message: str,
) -> Dict[str, Any]:
    return {
        "exp_name": exp_name,
        "scenario_id": _scenario_id(scenario),
        "nodes": nodes,
        "requests": requests,
        "sim_time": sim_time,
        "f_req": f_req,
        "t_mem": scenario.t_mem,
        "p_swap": scenario.p_swap,
        "link_fidelity": scenario.link_fidelity,
        "psw_threshold": scenario.psw_threshold,
        "enable_psw": enable_psw,
        "seed": seed,
        "run_index": run_index,
        "request_id": -1,
        "request_name": "",
        "finished": 0,
        "finish_time": None,
        "final_fidelity": None,
        "swap_wait_time_mean": None,
        "status": "error",
        "error_type": error_type,
        "error_message": error_message,
    }


def _build_summary_row(
    *,
    metrics: RunMetrics,
    scenario: Scenario,
    exp_name: str,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    enable_psw: bool,
    seed: int,
    run_index: int,
    status: str,
    error_type: Optional[str],
    error_message: Optional[str],
) -> Dict[str, Any]:
    wait_times = metrics.wait_times
    fidelities = metrics.final_fidelities
    avg_wait = _mean_or_none(wait_times)
    p50_wait = _percentile(wait_times, 50)
    p90_wait = _percentile(wait_times, 90)
    throughput = (
        _safe_div(metrics.finished, metrics.sim_span_slot)
        if metrics.sim_span_slot > 0
        else None
    )
    final_fidelity_mean = _mean_or_none(fidelities)
    final_fidelity_p10 = _percentile(fidelities, 10)
    swap_wait_mean = _mean_or_none(metrics.swap_wait_times)
    attempts_per_finished = _safe_div(metrics.psw_attempts, metrics.finished)

    return {
        "exp_name": exp_name,
        "scenario_id": _scenario_id(scenario),
        "nodes": nodes,
        "requests": requests,
        "sim_time": sim_time,
        "f_req": f_req,
        "t_mem": scenario.t_mem,
        "p_swap": scenario.p_swap,
        "link_fidelity": scenario.link_fidelity,
        "psw_threshold": scenario.psw_threshold,
        "enable_psw": enable_psw,
        "seed": seed,
        "run_index": run_index,
        "finished": metrics.finished,
        "avg_wait": avg_wait,
        "p50_wait": p50_wait,
        "p90_wait": p90_wait,
        "throughput": throughput,
        "final_fidelity_mean": final_fidelity_mean,
        "final_fidelity_p10": final_fidelity_p10,
        "swap_wait_time_mean": swap_wait_mean,
        "psw_attempts": metrics.psw_attempts,
        "psw_success": metrics.psw_success,
        "psw_fail": metrics.psw_fail,
        "psw_cancelled": metrics.psw_cancelled,
        "attempts_per_finished": attempts_per_finished,
        "status": status,
        "error_type": error_type,
        "error_message": error_message,
    }


def _build_error_summary_row(
    *,
    scenario: Scenario,
    exp_name: str,
    nodes: int,
    requests: int,
    sim_time: float,
    f_req: float,
    enable_psw: bool,
    seed: int,
    run_index: int,
    error_type: str,
    error_message: str,
) -> Dict[str, Any]:
    return {
        "exp_name": exp_name,
        "scenario_id": _scenario_id(scenario),
        "nodes": nodes,
        "requests": requests,
        "sim_time": sim_time,
        "f_req": f_req,
        "t_mem": scenario.t_mem,
        "p_swap": scenario.p_swap,
        "link_fidelity": scenario.link_fidelity,
        "psw_threshold": scenario.psw_threshold,
        "enable_psw": enable_psw,
        "seed": seed,
        "run_index": run_index,
        "finished": 0,
        "avg_wait": None,
        "p50_wait": None,
        "p90_wait": None,
        "throughput": None,
        "final_fidelity_mean": None,
        "final_fidelity_p10": None,
        "swap_wait_time_mean": None,
        "psw_attempts": 0,
        "psw_success": 0,
        "psw_fail": 0,
        "psw_cancelled": 0,
        "attempts_per_finished": None,
        "status": "error",
        "error_type": error_type,
        "error_message": error_message,
    }


def _fill_row(row: Mapping[str, Any], fieldnames: Sequence[str]) -> Dict[str, Any]:
    def _sanitize(value: Any) -> Any:
        return "" if value is None else value

    return {name: _sanitize(row.get(name)) for name in fieldnames}


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_fill_row(row, fieldnames))


def _add_deltas(rows: List[Dict[str, Any]]) -> None:
    index: Dict[Tuple[str, int, int], Dict[bool, Dict[str, Any]]] = {}
    for row in rows:
        key = (row.get("scenario_id"), row.get("seed"), row.get("run_index"))
        bucket = index.setdefault(key, {})
        bucket[bool(row.get("enable_psw"))] = row

    for bucket in index.values():
        row_off = bucket.get(False)
        row_on = bucket.get(True)
        if row_off is None or row_on is None:
            continue
        for metric in DELTA_TARGETS:
            on_val = row_on.get(metric)
            off_val = row_off.get(metric)
            if on_val is None or off_val is None:
                delta = None
            else:
                delta = on_val - off_val
            row_on[f"delta_{metric}"] = delta
            row_off[f"delta_{metric}"] = delta


def _iter_scenarios(
    *,
    t_mem_values: Iterable[float],
    p_swap_values: Iterable[float],
    link_fidelity_values: Iterable[float],
    psw_threshold_values: Iterable[float],
) -> Iterator[Scenario]:
    for t_mem in t_mem_values:
        for p_swap in p_swap_values:
            for link_fidelity in link_fidelity_values:
                for psw_threshold in psw_threshold_values:
                    yield Scenario(
                        t_mem=float(t_mem),
                        p_swap=float(p_swap),
                        link_fidelity=float(link_fidelity),
                        psw_threshold=float(psw_threshold),
                    )


def run_psw_sweep(
    *,
    exp_name: str,
    config: Mapping[str, Any],
    scenarios: Iterable[Scenario],
    run_dir: Path,
    enable_plots: bool = True,
) -> None:
    """PSW on/offの比較スイープを実行する。"""
    nodes = int(config.get("nodes", 50))
    requests = int(config.get("requests", 5))
    sim_time = float(config.get("sim_time", 300000))
    f_req = float(config.get("f_req", 0.8))
    seeds = list(config.get("seeds", [0]))
    runs_per_seed = int(config.get("runs_per_seed", 1))

    gen_rate = int(config.get("gen_rate", 50))
    memory_capacity = int(config.get("memory_capacity", 5))
    waxman_size = float(config.get("waxman_size", 100000))
    waxman_alpha = float(config.get("waxman_alpha", 0.2))
    waxman_beta = float(config.get("waxman_beta", 0.6))

    verbose_sim = bool(config.get("verbose_sim", False))

    raw_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for scenario in scenarios:
        logging.info(
            "シナリオ開始 t_mem=%s p_swap=%s link_fidelity=%s psw_threshold=%s",
            scenario.t_mem,
            scenario.p_swap,
            scenario.link_fidelity,
            scenario.psw_threshold,
        )
        for enable_psw in (False, True):
            for base_seed in seeds:
                for run_index in range(runs_per_seed):
                    seed = int(base_seed) + int(run_index)
                    models.T_MEM = float(scenario.t_mem)
                    try:
                        metrics = _run_single(
                            nodes=nodes,
                            requests=requests,
                            seed=seed,
                            sim_time=sim_time,
                            f_req=f_req,
                            p_swap=scenario.p_swap,
                            init_fidelity=float(scenario.link_fidelity),
                            enable_psw=enable_psw,
                            psw_threshold=float(scenario.psw_threshold),
                            gen_rate=gen_rate,
                            memory_capacity=memory_capacity,
                            waxman_size=waxman_size,
                            waxman_alpha=waxman_alpha,
                            waxman_beta=waxman_beta,
                            verbose_sim=verbose_sim,
                        )
                        summary_rows.append(
                            _build_summary_row(
                                metrics=metrics,
                                scenario=scenario,
                                exp_name=exp_name,
                                nodes=nodes,
                                requests=requests,
                                sim_time=sim_time,
                                f_req=f_req,
                                enable_psw=enable_psw,
                                seed=seed,
                                run_index=run_index,
                                status="ok",
                                error_type=None,
                                error_message=None,
                            )
                        )
                        raw_rows.extend(
                            _build_raw_rows(
                                metrics=metrics,
                                scenario=scenario,
                                exp_name=exp_name,
                                nodes=nodes,
                                requests=requests,
                                sim_time=sim_time,
                                f_req=f_req,
                                enable_psw=enable_psw,
                                seed=seed,
                                run_index=run_index,
                                status="ok",
                                error_type=None,
                                error_message=None,
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        logging.exception(
                            "実行失敗: scenario=%s enable_psw=%s seed=%s",
                            _scenario_id(scenario),
                            enable_psw,
                            seed,
                        )
                        error_type = type(exc).__name__
                        error_message = str(exc)
                        summary_rows.append(
                            _build_error_summary_row(
                                scenario=scenario,
                                exp_name=exp_name,
                                nodes=nodes,
                                requests=requests,
                                sim_time=sim_time,
                                f_req=f_req,
                                enable_psw=enable_psw,
                                seed=seed,
                                run_index=run_index,
                                error_type=error_type,
                                error_message=error_message,
                            )
                        )
                        raw_rows.append(
                            _build_error_raw_row(
                                scenario=scenario,
                                exp_name=exp_name,
                                nodes=nodes,
                                requests=requests,
                                sim_time=sim_time,
                                f_req=f_req,
                                enable_psw=enable_psw,
                                seed=seed,
                                run_index=run_index,
                                error_type=error_type,
                                error_message=error_message,
                            )
                        )

    _add_deltas(summary_rows)

    raw_path = run_dir / "raw.csv"
    summary_path = run_dir / "summary.csv"
    _write_csv(raw_path, raw_fieldnames(), raw_rows)
    _write_csv(summary_path, summary_fieldnames(), summary_rows)

    plot_dir = run_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    plot_ok = False
    if enable_plots:
        try:
            plot_ok = plot_delta_avg_wait(summary_rows, plot_dir)
        except Exception:
            logging.exception("プロット作成に失敗しました")
    if not plot_ok:
        (plot_dir / "placeholder.txt").write_text(
            "プロット対象データが不足しているため、今回はプレースホルダを出力しました。\n",
            encoding="utf-8",
        )

    write_readme(run_dir, config, summary_rows)


def plot_delta_avg_wait(
    summary_rows: Sequence[Mapping[str, Any]], plot_dir: Path
) -> bool:
    """delta_avg_waitの簡易プロットを作成する。"""
    import matplotlib.pyplot as plt

    rows = [
        r
        for r in summary_rows
        if str(r.get("status")) == "ok" and bool(r.get("enable_psw"))
    ]
    if not rows:
        return False

    points: Dict[Tuple[float, float], List[float]] = {}
    for row in rows:
        t_mem = float(row["t_mem"])
        p_swap = float(row["p_swap"])
        delta = row.get("delta_avg_wait")
        if delta is None:
            continue
        points.setdefault((t_mem, p_swap), []).append(float(delta))

    if not points:
        return False

    unique_t = sorted({k[0] for k in points})
    unique_p = sorted({k[1] for k in points})

    fig, ax = plt.subplots(figsize=(7, 4))
    if len(unique_t) > 1 and len(unique_p) > 1:
        import numpy as np

        grid = np.full((len(unique_t), len(unique_p)), float("nan"))
        for i, t_mem in enumerate(unique_t):
            for j, p_swap in enumerate(unique_p):
                vals = points.get((t_mem, p_swap))
                if vals:
                    grid[i, j] = float(mean(vals))
        im = ax.imshow(
            grid,
            origin="lower",
            aspect="auto",
            interpolation="nearest",
        )
        ax.set_xticks(range(len(unique_p)), [str(v) for v in unique_p])
        ax.set_yticks(range(len(unique_t)), [str(v) for v in unique_t])
        ax.set_xlabel("p_swap")
        ax.set_ylabel("t_mem")
        fig.colorbar(im, ax=ax, label="delta_avg_wait")
    else:
        xs = [k[0] for k in points.keys()]
        ys = [mean(points[k]) for k in points.keys()]
        ax.plot(xs, ys, marker="o", linestyle="-")
        ax.set_xlabel("t_mem")
        ax.set_ylabel("delta_avg_wait")

    ax.set_title("PSW差分: delta_avg_wait")
    fig.tight_layout()
    fig_path = plot_dir / "delta_avg_wait.png"
    fig.savefig(fig_path)
    plt.close(fig)
    return True


def _aggregate_by_scenario(
    summary_rows: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    bucket: Dict[str, List[Mapping[str, Any]]] = {}
    for row in summary_rows:
        if str(row.get("status")) != "ok":
            continue
        if not bool(row.get("enable_psw")):
            continue
        scenario_id = str(row.get("scenario_id"))
        bucket.setdefault(scenario_id, []).append(row)

    aggregated: List[Dict[str, Any]] = []
    for scenario_id, rows in bucket.items():
        deltas = [
            r.get("delta_avg_wait")
            for r in rows
            if r.get("delta_avg_wait") is not None
        ]
        delta_avg_wait = _mean_or_none([float(v) for v in deltas]) if deltas else None
        delta_throughput = _mean_or_none(
            [
                float(r["delta_throughput"])
                for r in rows
                if r.get("delta_throughput") is not None
            ]
        )
        delta_fidelity = _mean_or_none(
            [
                float(r["delta_final_fidelity_mean"])
                for r in rows
                if r.get("delta_final_fidelity_mean") is not None
            ]
        )
        delta_swap_wait = _mean_or_none(
            [
                float(r["delta_swap_wait_time_mean"])
                for r in rows
                if r.get("delta_swap_wait_time_mean") is not None
            ]
        )
        sample = rows[0]
        aggregated.append(
            {
                "scenario_id": scenario_id,
                "t_mem": float(sample["t_mem"]),
                "p_swap": float(sample["p_swap"]),
                "link_fidelity": float(sample["link_fidelity"]),
                "psw_threshold": float(sample["psw_threshold"]),
                "delta_avg_wait": delta_avg_wait,
                "delta_throughput": delta_throughput,
                "delta_final_fidelity_mean": delta_fidelity,
                "delta_swap_wait_time_mean": delta_swap_wait,
            }
        )
    return aggregated


def write_readme(
    run_dir: Path, config: Mapping[str, Any], summary_rows: Sequence[Mapping[str, Any]]
) -> None:
    """README.mdを生成する。"""
    scenario_stats = _aggregate_by_scenario(summary_rows)
    if scenario_stats:
        better = [s for s in scenario_stats if s["delta_avg_wait"] is not None and s["delta_avg_wait"] < 0]
        worse = [s for s in scenario_stats if s["delta_avg_wait"] is not None and s["delta_avg_wait"] > 0]
    else:
        better = []
        worse = []

    def _fmt_scenario(s: Mapping[str, Any]) -> str:
        return (
            f"t_mem={s['t_mem']}, p_swap={s['p_swap']}, "
            f"link_fidelity={s['link_fidelity']}, psw_threshold={s['psw_threshold']}"
        )

    lines = ["# 実験メモ", "", "- 実験条件:"]
    lines.append(
        f"  - nodes={config.get('nodes')} requests={config.get('requests')} sim_time={config.get('sim_time')} f_req={config.get('f_req')}"
    )
    sweep = config.get("sweep", {}) if isinstance(config.get("sweep"), dict) else {}
    lines.append(
        "  - sweep: t_mem=%s, p_swap=%s, link_fidelity=%s, psw_threshold=%s"
        % (
            sweep.get("t_mem"),
            sweep.get("p_swap"),
            sweep.get("link_fidelity"),
            sweep.get("psw_threshold"),
        )
    )
    lines.append(
        f"  - seeds={config.get('seeds')} runs_per_seed={config.get('runs_per_seed')}"
    )

    lines.append("- 観測された境界（PSWが効く/効かない領域）:")
    if better:
        lines.append("  - 効く側: " + "; ".join(_fmt_scenario(s) for s in better))
    else:
        lines.append("  - 効く側: まだ明確な差分なし")
    if worse:
        lines.append("  - 効かない側: " + "; ".join(_fmt_scenario(s) for s in worse))
    else:
        lines.append("  - 効かない側: まだ明確な差分なし")

    lines.append("- 悪化する条件とその兆候:")
    if worse:
        lines.append(
            "  - delta_avg_wait>0 のシナリオで待機悪化。swap_wait_time_mean増やPSW試行過多に注意。"
        )
    else:
        lines.append("  - 現状は明確な悪化兆候なし（要追加スイープ）")

    lines.append("- 次に掘るべき範囲:")
    if scenario_stats:
        sorted_stats = sorted(
            [s for s in scenario_stats if s["delta_avg_wait"] is not None],
            key=lambda s: abs(s["delta_avg_wait"]),
        )
        if sorted_stats:
            focus = sorted_stats[: min(3, len(sorted_stats))]
            lines.append(
                "  - 境界候補(差分が小さい条件)の周辺を細分化: "
                + "; ".join(_fmt_scenario(s) for s in focus)
            )
        else:
            lines.append("  - 境界候補が未確定のため全域の粗いスイープ継続")
    else:
        lines.append("  - 解析対象データ不足。まずはスイープを増やす")

    readme_path = run_dir / "README.md"
    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
