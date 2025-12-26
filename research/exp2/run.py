"""exp2実験ランナー。"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exp2 import common
from exp2 import run_dir


def _resolve_exp_name(config: Dict[str, Any], config_path: Path, override: str | None) -> str:
    if override:
        return override
    return (
        str(config.get("exp_name"))
        if config.get("exp_name")
        else str(config.get("experiment"))
        if config.get("experiment")
        else config_path.stem
    )


def _resolve_experiment_module(config: Dict[str, Any], exp_name: str) -> str:
    return str(config.get("experiment") or exp_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="exp2実験ランナー")
    common.add_common_args(parser)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = common.load_yaml(config_path)
    exp_name = _resolve_exp_name(config, config_path, args.exp_name)
    module_name = _resolve_experiment_module(config, exp_name)

    run_dir_path = run_dir.resolve_run_dir(exp_name, args.run_dir)
    common.setup_logging(run_dir_path)

    config_out = dict(config)
    config_out.setdefault("exp_name", exp_name)
    config_out.setdefault("experiment", module_name)
    config_out.setdefault("config_path", str(config_path))

    run_dir.write_config_yaml(run_dir_path, config_out)
    run_dir.write_config_md(
        run_dir_path,
        exp_name,
        config_out,
        required_keys=common.REQUIRED_CONFIG_KEYS,
    )

    module = importlib.import_module(f"exp2.experiments.{module_name}")
    if not hasattr(module, "run"):
        raise AttributeError(f"experiments.{module_name} にrun関数がありません")

    module.run(config=config_out, run_dir=run_dir_path, no_plots=args.no_plots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
