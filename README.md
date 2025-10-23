# 環境構築
## pythonの仮想環境構築
```bash
python3 -m venv .env
```
## qns(simQN)のインストール
```bash
pip install qns
```

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
