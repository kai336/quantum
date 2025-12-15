# 環境構築
## pythonの仮想環境構築
```bash
pip install uv
uv init
uv add qns
```
## pythonファイル実行
```bash
uv run hogehoge.py
```

# research/tests/test_param.py の使い方
EDPまわりの挙動を手早く試すためのシミュレーションスクリプト。`uv run` で直接実行でき、Waxmanトポロジや要求数などを引数で切り替えられます。

```bash
# デフォルト値のまま実行
uv run research/tests/test_param.py

# ノード数や要求数を変えて実行する例
uv run research/tests/test_param.py --nodes 100 --requests 10 --seed 123 --sim-time 2000000 --f-req 0.85
```

主要な引数:
- `--nodes` Waxmanトポロジに生成するノード数 (デフォルト: 50)
- `--requests` 生成する要求数 (デフォルト: 5)
- `--seed` 乱数シード (デフォルト: 42)
- `--sim-time` シミュレーション終了時刻 (デフォルト: 1000000)
- `--f-req` 最小要求忠実度 f_req (デフォルト: 0.8)

# 中身
<pre>
/quantum
    /archived
        /aopp   # とん挫したoppの改良バージョン
        /fidelity   # 忠実度に関するチュートリアル的な
        /opp    # opportunistic routingの実装
        /tutorials # SimQNのチュートリアル等
    /research # 進行中の研究
        /edp # EDPアルゴリズムに関する研究
            /alg # EDPアルゴリズム本体の実装
            /app # SimQNで動かすためのアプリケーションたち
            /sim  # フィデリティ等の計算モデルやトポロジー生成
            /exp # 実験で実行するファイル main.py
        /visualize # ネットワーク上のもつれ可視化(未着手)
</pre>
