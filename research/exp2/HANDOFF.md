# exp2 引継ぎメモ（PSW境界探索）

## 目的
- PSW(on/off)の効果（待ち時間・最終フィデリティ・スループットなど）を条件別に比較し、PSWが有効になる境界条件を特定する。

## 前提・運用ルール
- `research/exp` と `research/data` は凍結。以後は `research/exp2` で実験する。
- 出力先は `research/results/<timestamp>_<exp_name>/`。
- 各実験で `config.yaml` / `config.md` を保存。
- 成果物は `raw.csv` / `summary.csv` / `plots/*` / `README.md` を必ず出す。
- CSV列は `research/exp2/schema.py` に固定。
- PSW on/off は同一条件で対照実験し、`summary.csv` に delta_* を入れる。
- 失敗・例外はログと README に残す。

## 実装・構成
- ランナー: `research/exp2/run.py`
- 出力管理: `research/exp2/run_dir.py`
- 共通処理: `research/exp2/common.py`
- スキーマ: `research/exp2/schema.py`
- 実験定義: `research/exp2/experiments/psw_boundary.py`
- 設定YAML: `research/exp2/configs/*.yaml`
- 解析:
  - `research/exp2/analysis/summarize.py`
  - `research/exp2/analysis/plot_heatmap.py`
  - `research/exp2/analysis/plot_avgwait_compare.py`

## 重要な仕様メモ
- `sim_time` はタイムスロット単位（1秒=3000スロット）。
- QNSのシミュレータはイベントキューが空になれば終了し、`te`（sim_time）超のイベントは追加されない。
  - 無限ループではなくイベント数爆発で実時間が伸びる可能性が高い。
  - 根拠: `/home/kai/quantum/.venv/lib/python3.10/site-packages/qns/simulator/simulator.py` と `/home/kai/quantum/.venv/lib/python3.10/site-packages/qns/simulator/pool.py`
- 以後の方針として `sim_time=300000` に統一済み（全YAML更新済み、デフォルトも更新済み）。

## 直近の依頼内容（ユーザー指示）
- p_swap=0.2固定で、t_memを0.1〜1.0の各点を個別実行。
- タイムアウトは30分（実時間）。
- PSW on/offのavg_wait比較図を作成。
- まず無限ループ疑いを検証（→無限ループではなく実時間の長期化）。

## 実行結果の要点
### t_mem=0.1〜1.0（各点・sim_time=300000）
- 完走: t_mem=0.5, 0.6, 0.7, 0.8, 0.9, 1.0
- タイムアウト（30分）: t_mem=0.1, 0.2, 0.3, 0.4
- PSWのpurify試行は全点で `psw_attempts=0`（cancelのみ発生）
- avg_wait（PSW off/on）
  - t_mem=0.5: off=9493.0 / on=723.4
  - t_mem=0.6: off=1347.4 / on=672.4
  - t_mem=0.7: off=334.0 / on=334.0
  - t_mem=0.8: off=352.6 / on=352.6
  - t_mem=0.9: off=211.0 / on=211.0
  - t_mem=1.0: off=211.0 / on=211.0

### 実行フォルダ
- 比較図の出力先:
  - `research/results/20251226_023631_psw_boundary_tmem_095_points_compare/plots/avg_wait_psw_on_off.png`
- 個別実験出力（例）:
  - `research/results/*_psw_boundary_tmem_095_point_0p5/`
  - `research/results/*_psw_boundary_tmem_095_point_0p6/`
  - `research/results/*_psw_boundary_tmem_095_point_1p0/`
- タイムアウトで summary未生成だったフォルダには、補完用の `summary.csv` / `raw.csv` / `README.md` / `plots/placeholder.txt` を作成済み。

## 実行コマンド（再現用）
- 実験実行:
  - `uv run python research/exp2/run.py --config research/exp2/configs/psw_boundary_tmem_095_point_0p5.yaml`
- avg_wait比較図生成:
  - `uv run python research/exp2/analysis/plot_avgwait_compare.py --results-root research/results --exp-prefix psw_boundary_tmem_095_point_ --output research/results/20251226_023631_psw_boundary_tmem_095_points_compare/plots/avg_wait_psw_on_off.png`

## 次の課題候補
- t_mem<=0.4 の長時間ケースをどう完走させるか（sim_time短縮 or タイムアウト延長 or 条件緩和）。
- avg_wait差が大きい t_mem=0.5/0.6 の再現性検証（seeds増やす）。
- PSW purify発動（psw_attempts>0）を引き出す条件探索（swap待機を増やす設定など）。
