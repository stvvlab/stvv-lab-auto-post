# STVV LAB データベース更新エンジン

対象は既存の「STVV LAB｜戦術分析データベース」。8タブ、数式、書式、入力規則、出典URLを維持する。投稿処理とは別のPythonモジュール・GitHub Actionsで動く。

## 実装済みの範囲

- STVV公式の2025/26・2026/27日程ページを取得。試合日（日本時間）、相手、大会、ホーム/アウェイ、得失点をHTML要素単位で解析する。
- 試合IDを固定行番号として扱わず、シーズン・日付・相手・大会・会場区分で照合する。入力済みの結果が公式と食い違う場合は上書きせず、確認対象として報告する。
- 登録済み試合の空欄スコアのみ補完。元の出典URLと備考を維持して確認内容を追記し、既存入力規則に従って状態を更新する。PK敗退などの勝敗例外は維持する。
- 既存8タブの見出し、重複、孤立した試合ID、日付・イベント時刻の順、⑤の参照式・実効値、⑥⑦の試合数・勝敗集計を検証する。
- 書き込み直前に再読み込みして入力・書式・数式・メモ・入力規則が変わっていれば中止。書き込み後は別の読み込みで反映と無関係セルの保持を検証する。
- APIの書き込みタイムアウトを自動再試行しない。結果不明の場合は0件・不確定と報告する。APIがエラーでも別読み込みで全変更が確認できた場合だけ反映済みとする。
- 全書き込みは最小範囲のupdateCells。行・列・タブの削除/追加、並べ替え、数式の置換は実行しない。既存順序の不整合はレポートに出す。
- 専用の運用メモセルで、試合データを変えずに書き込みテストを行える。

## 未実装・未完了の範囲

この初期版だけで全データの補完が完了するわけではない。

- 新しい試合のID発番と行挿入は自動化していない。公式に存在して未登録の試合は確認対象にする。
- 得点イベント・選手別記録・戦術の転換点・詳細スタッツの自動登録は未実装。公式記事・UEFA個別記録を照合したアダプターを追加する必要がある。未確認数値を生成しない。
- UEFA統計の解析ヘルパーは大会集計のまま扱う。単一試合への自動転用は実装していない。
- 読み込み直後から書き込み直前のごく短い間の同時編集をSheets APIで原子的に防ぐことはできない。GitHub Actionsは同一concurrencyで直列化し、移行時にChatGPT側の書込タスクを停止して二重運転を避ける。

詳細調査は既存ChatGPTタスクで継続する。新エンジンの認証・書込テスト・定期実行を確認するまで既存タスクを止めない。

## 毎時実行

- 実行環境：GitHub-hosted ubuntu-latest、Python 3.12。
- Workflow：`.github/workflows/database-sync.yml` / `STVV Database Sync`。
- スケジュール：毎時17分（日本時間）。GitHubの混雑等で遅延する場合があり、分単位の定刻保証ではない。
- スケジュールの有効化にはmainへの反映が必要。ブランチだけでは毎時実行されない。
- 通常は監査のみ。Repository Variable `STVV_DB_WRITES_ENABLED=true` の場合だけ定期実行が書き込む。
- push時は認証済みでも監査のみ。PRではテストのみでGoogle認証を渡さない。
- レポートは各実行のSummaryと`database-report-…` artifact（JSON/Markdown、30日保持）。シート全文・認証情報・書込ペイロードをartifactへ出さない。
- 接続できなければ非ゼロ終了・追加0件/修正0件。緑色のテスト成功と、本番同期の成功は別々に判断する。

## 認証の初回設定（ユーザーによる操作が必要）

ChatGPTのGoogle接続をGitHubへ流用・コピーすることはできない。Googleのサービスアカウントをこの処理用に用意する。

1. 自分のGoogle CloudプロジェクトでGoogle Sheets APIを有効化し、サービスアカウントを作成する。既存のWorkspace全体への委任や管理者権限は不要。
2. 対象スプレッドシートだけをサービスアカウントの`client_email`へ「編集者」として共有する。
3. サービスアカウントのJSON鍵をGitHubのRepository Secret **STVV_DB_GOOGLE_CREDENTIALS**へ直接保存する。チャット・コード・ログへ貼らない。
4. Actions → STVV Database Sync → Run workflow → `audit`。Google接続と全8タブの監査成功を確認。
5. 既存ChatGPTの毎時タスクを一時停止し、Repository Variable **STVV_DB_WRITES_ENABLED**を`true`へ設定する。
6. `write-test`を実行し、`status=verified`、`verification=成功`、`note_cells=1`を確認する。結果不明やエラーなら変数をfalseに戻し、既存タスクを再開する。
7. 次のschedule起動で`verified`または`verified_no_change`を確認して、コードによる毎時結果照合の移行を完了とする。詳細データの調査・反映は別途移行する。

認証未設定・書込無効・定期実行未確認を「自動更新復旧完了」と扱わない。

設定画面： https://github.com/stvvlab/stvv-lab-auto-post/settings/secrets/actions

## ローカル実行

```bash
pip install -r config/database-requirements.txt
python -m unittest discover -s tests -p 'test_database.py' -v
python -m stvv_database                    # 監査と変更計画、書込なし
python -m stvv_database --apply            # Google認証で実更新・別読込検証
python -m stvv_database --apply --write-test
```

接続済みツールの読み取り結果を`--snapshot /private/path/snapshot.json`として渡し、同じエンジンで変更計画を作成できる。この場合`--apply`は禁止。計画内のfingerprintと直前再読を照合し、接続済みツールで書込後、`verify`で再読を検証する。`plan.private.json`には既存セル情報を含むためローカルだけで扱い、コミットしない。

公式仕様：
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate
- https://developers.google.com/identity/protocols/oauth2/service-account
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
