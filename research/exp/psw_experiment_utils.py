import csv
from pathlib import Path
from typing import Iterable, Mapping, Optional

from psw_request_waiting_exp import PSWStatsSummary


def format_optional_float(value: Optional[float], *, fmt: str = ".6g") -> str:
    return "" if value is None else format(value, fmt)


def extract_avg_wait(
    summaries: Iterable[PSWStatsSummary],
) -> tuple[Optional[float], Optional[float]]:
    avg_off = next((s.avg_wait_per_request for s in summaries if not s.enable_psw), None)
    avg_on = next((s.avg_wait_per_request for s in summaries if s.enable_psw), None)
    return avg_off, avg_on


def summarize_psw_stats(
    summaries: Iterable[PSWStatsSummary],
    base_fields: Mapping[str, object],
    *,
    float_fmt: str = ".6g",
) -> tuple[list[dict], dict]:
    summaries_list = list(summaries)
    long_rows: list[dict] = []
    wide_row: dict = dict(base_fields)

    for s in summaries_list:
        mode = "psw_on" if s.enable_psw else "psw_off"
        long_rows.append(
            {
                **base_fields,
                "mode": mode,
                "avg_wait_per_request_slot": format_optional_float(
                    s.avg_wait_per_request, fmt=float_fmt
                ),
                "total_finished": s.total_finished,
                "trial_count": s.trial_count,
                "psw_purify_attempts": s.psw_purify_attempts,
                "psw_purify_successes": s.psw_purify_successes,
                "psw_purify_fails": s.psw_purify_fails,
                "psw_cancelled": s.psw_cancelled,
                "psw_purify_attempts_per_finished": format_optional_float(
                    s.psw_purify_attempts_per_finished, fmt=float_fmt
                ),
            }
        )

        prefix = "on" if s.enable_psw else "off"
        wide_row[f"avg_wait_{prefix}_slot"] = format_optional_float(
            s.avg_wait_per_request, fmt=float_fmt
        )
        wide_row[f"total_finished_{prefix}"] = s.total_finished
        wide_row[f"trial_count_{prefix}"] = s.trial_count
        wide_row[f"psw_purify_attempts_{prefix}"] = s.psw_purify_attempts
        wide_row[f"psw_purify_successes_{prefix}"] = s.psw_purify_successes
        wide_row[f"psw_purify_fails_{prefix}"] = s.psw_purify_fails
        wide_row[f"psw_cancelled_{prefix}"] = s.psw_cancelled
        wide_row[f"psw_purify_attempts_per_finished_{prefix}"] = (
            format_optional_float(s.psw_purify_attempts_per_finished, fmt=float_fmt)
        )

    avg_off, avg_on = extract_avg_wait(summaries_list)
    if avg_off is not None and avg_on is not None:
        wide_row["avg_wait_delta_slot"] = format_optional_float(
            avg_on - avg_off, fmt=float_fmt
        )
        wide_row["avg_wait_ratio_on_over_off"] = format_optional_float(
            avg_on / avg_off, fmt=float_fmt
        )
    else:
        wide_row["avg_wait_delta_slot"] = ""
        wide_row["avg_wait_ratio_on_over_off"] = ""

    return long_rows, wide_row


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("no rows to write")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
