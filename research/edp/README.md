# EDP実験概要
## ディレクトリ構成
<pre>
/edp
    /alg
        edp.py # EDPアルゴリズムの本体
    /app
        node_app.py # 各ノード上で動くアプリケーション
        controller_app.py # セントラルコントローラで動くアプリケーション
        ports.py # セントラルコントローラと各ノードの橋渡し
    /sim
        link.py # リンクのクラス
        models.py # フィデリティ等計算モデル
        new_qchannnel.py # QuantumChannelにfidelity属性を追加
        new_request.py # Requestにswap_plan, swap_progress等を追加
        topology # waxmanトポロジー生成
    /exp
        main.py # シミュレーション実行プログラム
</pre>
## purpose
- the first step of simulating of EDP like algorithm on SimQN
- measuring swap-waiting time for established entanglement
- 最終的には対照実験 EDPlike vs EDPlike + ent.pumping while waiting for swap
## about
- 離散イベント駆動型
- routing & swapping algorithm: smth like EDP
- topology: line? grid? waxman?
## implementation details
  - QNode上で動くアプリケーション
    - コントローラアプリ (`ControllerApp`)
      - `install` でネットワーク・ノード一覧を保持し、自分自身を除外。`init_qcs` で `QuantumChannel` を `NewQC(fidelity_init=0.99)` に包んでおく。`init_reqs` で QNS の `net.requests` を `NewRequest`（`name`, `priority`, `f_req` を付与）に変換し、`batch_EDP` でスワップ計画 (`swap_plan=(root_op, ops)`) を前計算。
      - 初期イベントとして `gen_EP_routine`（各チャネルでリンクレベルEPを最大 `l0_link_max=5` まで生成、`NodeApp` のメモリ残量を確認しながら）、`request_handler_routine`（READYな `Operation` を実行し、全リクエスト完了でシミュレータ停止）、`links_manager_routine`（減衰管理の枠だけ用意）を投入。
      - 操作実行: `GEN_LINK` は空いている `LinkEP` を割り当て、見つからなければ `request_regen`。`SWAP` は左右EPを廃棄してから `p_swap=0.4` で成功判定し、`f_swap` で忠実度を更新した新EPを生成。`PURIFY` は `p_pur=0.9` で成功判定し、犠牲EPを消しつつ `f_pur` でfid更新; 失敗時はターゲットも削除して再生成要求。
    - ノードアプリ (`NodeApp`)
      - ノード毎のメモリ容量（デフォルト `memory_capacity=10`）と使用数を保持し、`has_free_memory/use_single_memory/free_single_memory` を提供。接続量子チャネルから隣接ノードリストも構築。
      - 初期イベントやスワップ・精製の本体は未実装のスタブ。
  - 新規クラス
    - `LinkEP` が各EPを管理（`fidelity`, `nodes`, `owner_op`, `is_free`, `swap_level` 等）。`ControllerApp.links` に蓄積し、所有権変更や削除でメモリ解放を行う。デコヒーレンス処理は未実装。
    - `NewQC`: `QuantumChannel` にリンク生成時の初期忠実度 `fidelity_init` を付与。
    - `NewRequest`: QNS `Request` を拡張し、`name`, `priority`, `f_req`, `swap_plan`, `swap_progress`, `reserve_links`, `is_done` を保持。
    - `Operation`: スワップ計画のノード。`OpType`（`GEN_LINK`/`SWAP`/`PURIFY`）、`OpStatus`（`WAITING`/`READY`/`RUNNING`/`DONE`/`RETRY`）、`n1/n2/via`、`parent/children`、生成・所有する `LinkEP`（`ep`/`pur_eps`）を保持。`can_run/judge_ready/request_regen` などで実行条件や再生成を管理。
  - スワップ計画・操作木
    - `edp.alg.edp.EDP` が `query_route` で得た最短経路のうち最初の候補を使い、`NewQC` のレート/忠実度（現状fidは固定0.99）と `f_req` を基にスワップ・精製を探索。結果の木を `build_ops_from_edp_result` で `Operation` (`OpType`=`GEN_LINK`/`SWAP`/`PURIFY`, `OpStatus`=`WAITING`/`READY`/`RUNNING`/`DONE`/`RETRY`) の木に変換。
    - `Operation.request_regen` で必要なEP再生成のフラグを立て、`PURIFY` は子のEP所有権を引き継ぐ処理を持つ。
