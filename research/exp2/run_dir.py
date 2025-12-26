"""結果ディレクトリ生成と設定ファイル出力。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "results"


def _sanitize_name(name: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in name)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_run_dir(exp_name: str, timestamp: str | None = None) -> Path:
    timestamp = timestamp or _timestamp()
    base = f"{timestamp}_{_sanitize_name(exp_name)}"
    run_dir = RESULTS_ROOT / base
    if not run_dir.exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    suffix = 2
    while True:
        candidate = RESULTS_ROOT / f"{base}_{suffix}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        suffix += 1


def resolve_run_dir(exp_name: str, run_dir: str | Path | None) -> Path:
    if run_dir is not None:
        path = Path(run_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return create_run_dir(exp_name)


def _fmt_value(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _get_by_path(config: Mapping[str, Any], path: str) -> object:
    current: object = config
    for key in path.split("."):
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def write_config_yaml(run_dir: Path, config: Mapping[str, Any]) -> Path:
    path = run_dir / "config.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
    return path


def write_config_md(
    run_dir: Path,
    exp_name: str,
    config: Mapping[str, Any],
    required_keys: Iterable[str],
) -> Path:
    config_path = run_dir / "config.md"
    required_keys = list(required_keys)
    lines = [
        "# 実験設定",
        "",
        f"- 実験名: {exp_name}",
        f"- 作成日: {datetime.now().strftime('%Y-%m-%d')} ",
        "",
        "## 必須パラメータ",
        "| 項目 | 値 |",
        "| --- | --- |",
    ]
    for key in required_keys:
        value = _get_by_path(config, key)
        lines.append(f"| {key} | {_fmt_value(value)} |")

    extra_keys = [k for k in config.keys() if k not in required_keys]
    if extra_keys:
        lines += ["", "## その他パラメータ", "| 項目 | 値 |", "| --- | --- |"]
        for key in extra_keys:
            lines.append(f"| {key} | {_fmt_value(config.get(key))} |")

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path
