"""
exp2のCSVスキーマ定義（列名・型・意味の唯一のソース）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Column:
    """CSV列の定義。"""

    name: str
    dtype: str
    description: str


RAW_COLUMNS: List[Column] = [
    Column("exp_name", "str", "実験名"),
    Column("scenario_id", "str", "シナリオ識別子"),
    Column("nodes", "int", "ノード数"),
    Column("requests", "int", "リクエスト数"),
    Column("sim_time", "float", "シミュレーション時間(スロット)"),
    Column("f_req", "float", "要求フィデリティ"),
    Column("t_mem", "float", "メモリ寿命T_MEM"),
    Column("p_swap", "float", "スワップ成功確率"),
    Column("link_fidelity", "float", "リンク初期フィデリティ"),
    Column("psw_threshold", "float", "PSW閾値"),
    Column("enable_psw", "bool", "PSW有効フラグ"),
    Column("seed", "int", "使用シード"),
    Column("run_index", "int", "シード内の反復番号"),
    Column("request_id", "int", "リクエストID"),
    Column("request_name", "str", "リクエスト名"),
    Column("finished", "int", "完了フラグ(1/0)"),
    Column("finish_time", "float", "完了時刻(スロット)"),
    Column("final_fidelity", "float", "完了時フィデリティ"),
    Column("swap_wait_time_mean", "float", "リクエスト内平均swap待機"),
    Column("status", "str", "実行状態(ok/error)"),
    Column("error_type", "str", "例外型"),
    Column("error_message", "str", "例外メッセージ"),
]

SUMMARY_COLUMNS: List[Column] = [
    Column("exp_name", "str", "実験名"),
    Column("scenario_id", "str", "シナリオ識別子"),
    Column("nodes", "int", "ノード数"),
    Column("requests", "int", "リクエスト数"),
    Column("sim_time", "float", "シミュレーション時間(スロット)"),
    Column("f_req", "float", "要求フィデリティ"),
    Column("t_mem", "float", "メモリ寿命T_MEM"),
    Column("p_swap", "float", "スワップ成功確率"),
    Column("link_fidelity", "float", "リンク初期フィデリティ"),
    Column("psw_threshold", "float", "PSW閾値"),
    Column("enable_psw", "bool", "PSW有効フラグ"),
    Column("seed", "int", "使用シード"),
    Column("run_index", "int", "シード内の反復番号"),
    Column("finished", "int", "完了リクエスト数"),
    Column("avg_wait", "float", "平均待機時間"),
    Column("p50_wait", "float", "待機時間のP50"),
    Column("p90_wait", "float", "待機時間のP90"),
    Column("throughput", "float", "スループット"),
    Column("final_fidelity_mean", "float", "最終フィデリティ平均"),
    Column("final_fidelity_p10", "float", "最終フィデリティP10"),
    Column("swap_wait_time_mean", "float", "swap待機時間平均"),
    Column("psw_attempts", "int", "PSW試行数"),
    Column("psw_success", "int", "PSW成功数"),
    Column("psw_fail", "int", "PSW失敗数"),
    Column("psw_cancelled", "int", "PSW中止数"),
    Column("attempts_per_finished", "float", "完了当たりPSW試行"),
    Column("status", "str", "実行状態(ok/error)"),
    Column("error_type", "str", "例外型"),
    Column("error_message", "str", "例外メッセージ"),
    Column("delta_finished", "float", "完了数差分(PSW on - off)"),
    Column("delta_avg_wait", "float", "平均待機差分"),
    Column("delta_p50_wait", "float", "P50待機差分"),
    Column("delta_p90_wait", "float", "P90待機差分"),
    Column("delta_throughput", "float", "スループット差分"),
    Column("delta_final_fidelity_mean", "float", "最終フィデリティ平均差分"),
    Column("delta_final_fidelity_p10", "float", "最終フィデリティP10差分"),
    Column("delta_swap_wait_time_mean", "float", "swap待機平均差分"),
    Column("delta_attempts_per_finished", "float", "試行/完了差分"),
]

DELTA_TARGETS: List[str] = [
    "finished",
    "avg_wait",
    "p50_wait",
    "p90_wait",
    "throughput",
    "final_fidelity_mean",
    "final_fidelity_p10",
    "swap_wait_time_mean",
    "attempts_per_finished",
]


def raw_fieldnames() -> List[str]:
    return [c.name for c in RAW_COLUMNS]


def summary_fieldnames() -> List[str]:
    return [c.name for c in SUMMARY_COLUMNS]
