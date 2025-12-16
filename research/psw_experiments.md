# PSW関連実験メモ

## 既存データの確認
- `tests/pumping_compare.py`のp_swapスイープ結果 (`data/psw_compare.csv` / `data/psw_compare.png`) を確認。p_swap=0.2–0.6でPSW on/offの平均完了時間が全て一致。
- `data/swap_waiting_results.csv`より、swap待機はp_swap=0.2–0.6で平均8–27 slot程度。

## 追加で実施したコマンドと結果
- 基本条件でPSW有無を再確認  
  ```bash
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python exp/psw_request_waiting_exp.py
  ```  
  出力: `off,27.38,50,243` / `on,27.38,50,243`（平均待ち時間slot, trial, finish）

- デコヒーレンスを強めても差分が出るかの試行（T_MEMを短縮）  
  ```bash
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python python - <<'PY'
  from exp.psw_request_waiting_exp import compare_psw_on_off
  from edp.sim import models

  models.T_MEM = 0.01  # メモリ寿命を短縮
  summaries = compare_psw_on_off(
      seeds=[0],
      runs_per_seed=1,
      nodes=10,
      requests=2,
      sim_time=20_000,
      f_req=0.8,
      p_swap=0.4,
      init_fidelity=0.99,
      verbose_sim=False,
      psw_threshold=0.9,
  )
  for s in summaries:
      flag = "on" if s.enable_psw else "off"
      avg = "" if s.avg_wait_per_request is None else f"{s.avg_wait_per_request:.2f}"
      print(flag, avg, s.total_finished)
  PY
  ```  
  出力: `off 4.00 1` / `on 4.00 1`（待ち時間は短く、差分なし）

- さらにT_MEM=0.01でノード数20・種2など大きめ条件、T_MEM=0.0001でp_swap=0.1なども試行したが、計算負荷が高く120秒タイムアウトし結果なし。

## 現状の示唆
- デコヒーレンスモデルではT_MEM=1000 sかつ待機が数十slot（数十µs）しかないため、psw_threshold(0.9)を下回らずPSWが発動しない。
- T_MEMを大幅に縮めても今回の小規模設定では待機が短すぎ、PSWの効果差は確認できず。
