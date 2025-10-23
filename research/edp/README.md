# EDP実験概要
## ディレクトリ構成
```
/edp
    /alg
        edp.py # EDPアルゴリズムの本体
    /app
        node_app.py # 各ノード上で動くアプリケーション
        controller_app.py # セントラルコントローラで動くアプリケーション
        ports.py # セントラルコントローラと各ノードの橋渡し
    /core
        models.py # フィデリティ等計算モデル
        topology # waxmanトポロジー生成
    /exp
        main.py # シミュレーション実行プログラム
```
## purpose
- the first step of simulating of EDP like algorithm on SimQN
- measuring swap-waiting time for established entanglement
- 最終的には対照実験 EDPlike vs EDPlike + ent.pumping while waiting for swap
## about
- 離散イベント駆動型
- routing & swapping algorithm: smth like EDP
- topology: line? grid? waxman?
## implementation details
  - ノード上のアプリケーション
    - ``
  - パラメタ
    - `gen_rate`: p_genのかわりにもつれ生成のレートを決定
    - `p_swap`
    - `p_pur`
  - リクエスト `Request: net.requests[i]` の属性
    - `QNode: src`: the source node
    - `QNode: dst`: the destination node
    - `Dist: attr`: the attributes of the request
      - `["id"]`: UUID
      - `["swapping"]`: swappingの計画&進捗
        - `plan`: swapping tree(EDPの出力)に記された操作の順序列
        - `progress`: treeで指定された操作の進捗
      - `["fidelity_threshold"]`: 要求EP忠実度の下限
      - `["priority"]`: 優先度
      - `["status"]`: "queuing" | "performing" | "success" | "fail"
      - `["purification"]`: 精製ポリシーのobject
        - `is_enabled`
        - `is_pumping`
      - `["resource_hints"]`: 資源制約
        - `max_mem_per_node`: ノードのメモリ数
        - `reserve_links`: 専有したいリンクのid配列 経路決定後
  - ノード `QNode: net.nodes[j]` の属性
    - `network`: 属するネットワーク
    - `cchannels`, `qchannels`: 接続された古典・量子チャネル
    - `memories`: # of memories にする
    - `operators`: ?
    - `croute_table`, `qroute_table`: 古典・量子のルーティングテーブル
    - `requests`: `List[Request]`自分が送信者となるリクエストの配列
    - `apps`: `List[Application]`
  - swapの待ち時間を計測する
    - `t_ready_left`, `t_ready_right`
      - swapに用いる左右のもつれができたそれぞれの時間
    - `t_swap_start`
      - swap処理を開始した時刻
