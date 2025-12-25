# PSW関連実験メモ

## 既存データの確認
- `tests/pumping_compare.py`のp_swapスイープ結果 (`data/YYYYMMDD_psw_compare/psw_compare.csv` / `data/YYYYMMDD_psw_compare/psw_compare.png`) を確認。p_swap=0.2–0.6でPSW on/offの平均完了時間が全て一致。
- `data/YYYYMMDD_swap_waiting/swap_waiting.csv`より、swap待機はp_swap=0.2–0.6で平均8–27 slot程度。

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

## 追加試行: 閾値を高めてPSWを強制
- タイムスロットは1/3000 sなので、待機が数十slotの場合はT_MEM=0.01でもフィデリティ劣化が小さく、psw_threshold=0.9ではPSWがほぼ発動しない。一方、T_MEMを極端に縮めるとイベント数が爆発し120sタイムアウトになるケースが多かった。
- 対策としてpsw_thresholdを初期フィデリティ(0.99)より高め(0.995)に設定し、swap待機が発生したら必ずPSWを走らせる条件で比較。
- 実行コマンド（出力は `data/YYYYMMDD_psw_threshold_force/` を想定）:
  ```bash
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python - <<'PY'
  from exp.psw_request_waiting_exp import compare_psw_on_off
  from edp.sim import models

  models.T_MEM = 1000  # デフォルト
  params = dict(
      seeds=[0, 1],
      runs_per_seed=2,
      nodes=30,
      requests=10,
      sim_time=500_000,
      f_req=0.8,
      init_fidelity=0.99,
      verbose_sim=False,
  )

  for p_swap, threshold in [(0.2, 0.995), (0.2, 0.9), (0.1, 0.995)]:
      summaries = compare_psw_on_off(psw_threshold=threshold, p_swap=p_swap, **params)
      for s in summaries:
          flag = "on" if s.enable_psw else "off"
          avg = "" if s.avg_wait_per_request is None else f"{s.avg_wait_per_request:.2f}"
          print(p_swap, threshold, flag, avg, s.total_finished, s.trial_count)
  PY
  ```
- 出力（avg_wait_per_request_slot, total_finished, trial_count）:
  - p_swap=0.2, threshold=0.995 → off 365.15 / on 282.38, 39, 4
  - p_swap=0.2, threshold=0.9 → off 365.15 / on 365.15, 39, 4
  - p_swap=0.1, threshold=0.995 → off 1494.00 / on 978.85, 39, 4
- 所感: threshold=0.9では差分なし。thresholdを0.995に上げると、デコヒーレンスが小さい条件でもPSWが発動し平均待機スロットが短縮（完了数は同じ）。イベント爆発を避けつつ現実的な差分を得るには、T_MEMとタイムスロットスケールを再調整する必要がある。

## 追加試行: しきい値×p_swapスイープ + PSW発火回数の可視化
- `ControllerApp`にPSWの統計カウンタ（purify試行/成功/失敗/キャンセル）を追加し、PSWが本当に動いているかを数値で追えるようにした。
- 実行（`data/YYYYMMDD_psw_threshold_sweep/psw_threshold_sweep_long.csv` / `data/YYYYMMDD_psw_threshold_sweep/psw_threshold_sweep_wide.csv`に保存）:
  ```bash
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python exp/psw_threshold_sweep_exp.py
  ```
- 可視化（英語ラベルPNGを同じ実験フォルダへ出力）:
  ```bash
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python visualize/plot_psw_threshold_sweep.py
  ```

## 追加試行: T_MEMスイープ（p_swap=0.2, gen_rate=50, threshold=0.95固定）
- スクリプト: `exp/psw_tmem_sweep_exp.py`（タイムアウト/追記/シード・シミュレーション時間指定に対応）
- 1シナリオあたりのタイムアウトを設定して長時間実行を制御（デフォルト15分、`--scenario-timeout-sec`）。
- 現状の実行:
  ```bash
  # まずデフォルト条件（種0,1×2回, sim_time=500000）を実行
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python exp/psw_tmem_sweep_exp.py --scenario-timeout-sec 900
  # 未完了分を条件を絞って追記したい場合（例: seed=0, run=1, sim_time短縮）
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python exp/psw_tmem_sweep_exp.py --append --t-mem 0.1 --seeds 0 --runs-per-seed 1 --sim-time 200000 --scenario-timeout-sec 900
  ```
- 現在の結果（デフォルト条件、15分タイムアウト）:
  - 完了: T_MEM = 1000, 10, 1 → `data/YYYYMMDD_psw_tmem_sweep/psw_tmem_sweep_long.csv` / `data/YYYYMMDD_psw_tmem_sweep/psw_tmem_sweep_wide.csv`
  - タイムアウト: T_MEM = 0.1, 0.02, 0.01（15分で打ち切り。条件を軽くして追記可）
- 可視化:
  ```bash
  UV_CACHE_DIR=./.uv_cache uv run --project .. --offline --no-sync --python /home/kai/quantum/.venv/bin/python visualize/plot_psw_tmem_sweep.py
  # 出力: data/YYYYMMDD_psw_tmem_sweep/psw_tmem_sweep_wait.png, data/YYYYMMDD_psw_tmem_sweep/psw_tmem_sweep_psw_rate.png
  ```
