from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"


def _sanitize_name(name: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in name)


def create_run_dir(exp_name: str, date_str: str | None = None) -> Path:
    date_str = date_str or datetime.now().strftime("%Y%m%d")
    base = f"{date_str}_{_sanitize_name(exp_name)}"
    run_dir = DATA_ROOT / base
    if not run_dir.exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    suffix = 2
    while True:
        candidate = DATA_ROOT / f"{base}_{suffix}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        suffix += 1


def resolve_run_dir(
    exp_name: str, run_dir: str | Path | None, date_str: str | None = None
) -> Path:
    if run_dir is not None:
        path = Path(run_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return create_run_dir(exp_name, date_str)


def find_latest_run_dir(exp_name: str) -> Path | None:
    if not DATA_ROOT.exists():
        return None
    suffix = _sanitize_name(exp_name)
    candidates = list(DATA_ROOT.glob(f"*_{suffix}*"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _fmt_value(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value)


def write_config_md(
    run_dir: Path,
    exp_name: str,
    params: Mapping[str, object],
    required_keys: Iterable[str],
) -> Path:
    config_path = run_dir / "config.md"
    required_keys = list(required_keys)
    lines = [
        "# Experiment Config",
        "",
        f"- name: {exp_name}",
        f"- date: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Required Parameters",
        "| name | value |",
        "| --- | --- |",
    ]
    for key in required_keys:
        lines.append(f"| {key} | {_fmt_value(params.get(key))} |")
    extra_keys = [k for k in params.keys() if k not in required_keys]
    if extra_keys:
        lines += ["", "## Other Parameters", "| name | value |", "| --- | --- |"]
        for key in extra_keys:
            lines.append(f"| {key} | {_fmt_value(params.get(key))} |")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path
