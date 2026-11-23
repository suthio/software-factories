# OK：TODOアプリを作って、チケットで機能を足す

まずは、付属のTODOアプリに「完了したタスクだけ見たい」というチケットを1枚渡します。AIが絞り込みを追加し、テストに落ちたら結果を受け取って直します。うまくいったら、同じアプリに未完了の件数も表示させてみましょう。

## 1枚目：絞り込みを追加する

macOS・Linuxで Python 3.8以上、認証済みのCodex CLI、`uvx` を用意します。AIが書いたコードを実行するので、普段使いの認証情報や本番への書き込み権限がない隔離環境で試してください。

普段のCodex設定で実行できない場合は、`SOFTWARE_FACTORY_CODEX_MODEL` に自分のアカウントで使えるモデルを指定します。`SOFTWARE_FACTORY_CODEX_EFFORT` で推論の設定も変えられます。どちらも環境変数を渡した実行だけに適用されます。

この作例は2026年11月22日に `gpt-5.6-luna`、推論設定 `low` で実行し、1枚目・2枚目ともにテストに通ることを確認しました。

リポジトリのルートで実行します。付属のアプリにはタスクの追加・完了・削除と保存が入っています。絞り込みも未完了件数の表示もありません。

```sh
example=examples/OK/05-todo-factory
state=$(mktemp -d)
python3 "$example/improve.py" "$state" --init "$example/starter/app.py" &&
  python3 "$example/improve.py" "$state" --ticket "$example/tickets/001-status-filter.json"
```

`--init` は付属のアプリをテストし、コピーを登録します。`--ticket` を実行したあとは、合否の判断も修正の指示も不要です。Ruffでコードを調べ、HTTPで実際にタスクを追加したり、絞り込んだりします。落ちたら結果をAIに渡し、最初の試行を含めて最大3回試します。

## 2枚目：絞り込みを残したまま件数を表示する

1枚目が `passed` になったら、同じ `state` を使って2枚目を渡します。件数が合っていても、絞り込みが壊れたら不合格です。やり直しても通らなければ、`current/app.py` は切り替わらず、絞り込みが動くアプリを使い続けられます。

```sh
python3 "$example/improve.py" "$state" --ticket "$example/tickets/002-remaining-count.json"
```

2枚を続けて処理するなら、2つの `--ticket` コマンドを `&&` でつなげます。1枚目が通ったときだけ2枚目に進みます。`--ticket` の終了コードは、合格なら `0`、試行上限まで通らなければ `1`、実行時のエラーなら `2` です。

```sh
python3 "$state/current/app.py" --port 8000 --data "$state/todos.json"
```

`http://127.0.0.1:8000/` で操作できます。サーバーを起動したままチケットを処理した場合は、起動し直すと変更が見えます。本番への反映やデータの移行はしません。

発表では、一覧を絞り込めることと未完了の件数が出ることを見せます。次に `results/` の結果と、`runs/` にある2枚目の `build.log` を開きます。1枚目のテスト `status-filter` も、2枚目のテスト `remaining-count` も実行したことが分かります。

## 3枚目を足す、チケットの到着を待つ

チケットの `request` に依頼を書き、`acceptance` にテスト名を入れます。新しい機能を試すなら、[受け入れ条件](acceptance/)と [`build/check.py`](build/check.py) のテストを先に用意します。合格したチケットのテストは、次回以降も毎回実行します。動作はHTTPでテストします。見た目やアクセシビリティは判定しません。

`inbox/` にチケットを置く方法もあります。書きかけのJSONを読まないよう、いったん `.tmp` で置き、コピーが終わってから `.json` に名前を変えます。`--once` はその時点のチケットをファイル名順に処理します。`--watch` は起動している間、5秒ごとに確認します。この2つのモードでは、落ちたチケットがあっても次に進みます。処理済みのファイル名は読み直しません。GitHubに接続する必要はありません。

## アプリ本体もAIに作らせる

付属のアプリを使わず、[題材メモ](brief.md)から作ることもできます。AIが計画を書き、別の呼び出しで実装します。Ruffと基本動作のテストを通ったら、出力された `release/app.py` を `--init` に渡せます。途中で止まった場合は、`report.json` と工程ごとのログを確認してください。

```sh
python3 examples/OK/05-todo-factory/factory.py
```

## 計画あり・なしを比べる

発表では先に `release/app.py` を操作して見せ、次に `plan/plan.json` と `build.log` を開きます。同じ題材・同じ検査で「計画あり」と「計画なし」を比べるなら、次のコマンドは計画を省いて実装から始めます。合格までの試行回数と、詰まった箇所を見比べてみてください。

```sh
python3 examples/OK/factory.py examples/OK/05-todo-factory/build --brief examples/OK/05-todo-factory/brief.md
```
