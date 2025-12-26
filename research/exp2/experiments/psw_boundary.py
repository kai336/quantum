"""PSW境界探索用のスイープ定義。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .. import common


def _values(config: Dict[str, Any], key: str, default: Iterable[float]) -> List[float]:
    sweep = config.get("sweep", {}) if isinstance(config.get("sweep"), dict) else {}
    if key in sweep and sweep[key] is not None:
        return list(sweep[key])
    if key in config and config[key] is not None:
        return [float(config[key])]
    return [float(v) for v in default]


def build_scenarios(config: Dict[str, Any]) -> List[common.Scenario]:
    """YAML設定からシナリオ群を作る。"""
    t_mem_values = _values(config, "t_mem", [1000.0])
    p_swap_values = _values(config, "p_swap", [0.4])
    link_fidelity_values = _values(
        config,
        "link_fidelity",
        [float(config.get("init_fidelity", 0.99))],
    )
    psw_threshold_values = _values(config, "psw_threshold", [0.9])

    scenarios: List[common.Scenario] = []
    for t_mem in t_mem_values:
        for p_swap in p_swap_values:
            for link_fidelity in link_fidelity_values:
                for psw_threshold in psw_threshold_values:
                    scenarios.append(
                        common.Scenario(
                            t_mem=float(t_mem),
                            p_swap=float(p_swap),
                            link_fidelity=float(link_fidelity),
                            psw_threshold=float(psw_threshold),
                        )
                    )
    return scenarios


def run(*, config: Dict[str, Any], run_dir, no_plots: bool = False) -> None:
    """PSW境界探索を実行する。"""
    exp_name = str(config.get("exp_name", "psw_boundary"))
    scenarios = build_scenarios(config)
    common.run_psw_sweep(
        exp_name=exp_name,
        config=config,
        scenarios=scenarios,
        run_dir=run_dir,
        enable_plots=not no_plots,
    )
