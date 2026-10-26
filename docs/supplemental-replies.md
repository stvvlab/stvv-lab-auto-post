# 公開済み投稿への補足・分析リプ

ユーザーが求めているのは、`@stvvlabo` が公開済みの自分の投稿へ、確認済みの補足・分析を後から返信として追加すること。指標レポート、新しい単独投稿、既存の親を再投稿する新規threadは代用にしない。

## 2026-10-24の実測結果

送信機能は未完成。無料・認証済み・無人で公開済みX投稿へ後付け返信できる経路は確認できなかったため、実リプとテスト投稿は行っていない。

### Buffer

- Buffer GraphQL APIの`metadata.twitter.thread`は、親を含む全投稿を一度に渡し、順番に公開する新規thread用。
- 公式型定義でも、thread配列の最初がrootで、top-level textと一致させる必要がある。
- 公開済みX投稿IDを返信先として渡すフィールドは公開仕様にない。
- したがって、既存投稿をrootとして再送したり、新しい単独投稿へフォールバックしたりしない。

公式資料：

- https://developers.buffer.com/types/TwitterPostMetadataInput.html
- https://developers.buffer.com/examples/create-threaded-post.html
- https://support.buffer.com/articles/using-buffers-api-GtIYIQilz5

### Metricool

- 接続済みMetricool MCPで公開されているX書き込みは、新規の予約投稿作成・予約投稿更新・レビュー送付。既存投稿へのreplyツールはない。
- `createScheduledPost`のX仕様は単一投稿のみで、thread分割も禁止されている。
- 実際に2つのMetricoolリンクを読み取り確認したが、対象brand `7113222` は「接続済みSNSなし」と返った。ChatGPT側へのMetricool接続と、Metricool brandへのX接続は別状態。
- Metricool公式ヘルプでは、Xの公開コメントはInboxで扱えず、X InboxはDMのみ。X threadは全体を同じ日時に公開する仕様で、公開済みthreadへの追記ではない。
- X連携はStarter以上とX add-onが必要。2026-07-13以降の公式価格は1アカウント月額10ドル／10ユーロ（年額120ドル／120ユーロ）。この契約や課金は実施していない。

公式資料：

- https://help.metricool.com/inbox-manager-how-to-manage-messages-and-comments-from-metricool-s9zze
- https://help.metricool.com/comments-or-messages-not-appearing-in-inbox-tmofe
- https://help.metricool.com/how-to-schedule-threads-in-metricool-qq3fr
- https://help.metricool.com/your-guide-to-the-x-twitter-add-on-wt5wy

### X公式API

- `POST /2/tweets`はreplyオブジェクトを持ち、OAuthで認証した本人アカウントから返信できる正規経路。
- ただしX APIは従量課金。2026-10-24確認時の公式料金はPost作成1リクエスト0.015ドル、URL付きPost作成0.200ドル。
- Developer Consoleでクレジット購入、アプリ作成、ユーザー認証が必要。無断で契約・購入・キー作成はしない。

公式資料：

- https://docs.x.com/x-api/posts/create-post
- https://docs.x.com/x-api/getting-started/pricing

## 今回実装した安全基盤

`supplemental_replies.py`と`editorial/supplemental_replies.json`を追加した。送信手段は接続していないが、次の事故防止をテスト可能な状態で準備した。

1. 親URLを`https://x.com/stvvlabo/status/<数字ID>`に限定する。
2. 親keyが`posted.json`のpublication historyに一意に存在することを確認する。
3. 公式HTTPS出典を本文に表示し、reviewedかつreadyの候補だけを受け付ける。
4. `親投稿ID＋補足本文＋公式出典`のSHA-256で一意キーを作る。
5. 将来の送信前に`pending_replies`を永続保存する。
6. 結果不明はpendingを残し、同じ内容を再送しない。
7. X上の返信URLと親投稿IDの関係を確認できた場合だけpublishedへ移す。
8. transport未設定時は`blocked_no_reply_transport`で停止し、単独投稿へ変更しない。

現在登録している親対応は、X表示確認済みの3件（ミッティラン、ハイドゥク無観客、ブルージュ結果）。返信候補は0件で、queueは無効。公式一次情報から未掲載の補足が確認できるまで本文を捏造しない。

## 2026-10-26の対応付け検証強化

従来は「自分のX投稿URL」と「履歴にあるkey」を別々に確認しており、別の自分の投稿IDを誤ってそのkeyに組み合わせる余地があった。親レジストリを必須にし、親key・X URL・投稿ID・owner・verified・実投稿本文・Buffer ID・元の公式出典が履歴と一致することを、pendingを保存する前に照合するよう修正した。親keyの登録なし・重複・内容変更・レジストリ読取失敗は停止する。

3件の対応付けは公開済みmanifestのX表示確認記録とposted.jsonに基づく。新しいX表示確認や返信送信を行ったという意味ではない。送信手段は引き続き未接続であり、完了扱いにしない。

## 完了に必要な選択

次のいずれかが必要。

1. X公式APIの従量課金とOAuth設定を明示的に承認する。
2. 将来、Bufferまたは接続ツールが公開済み投稿へのreplyを正式対応する。
3. 無料のまま進める場合、システムが親URL付きの確認済み下書きを用意し、ユーザーがX公式画面で手動返信する運用にする。

選択がない間は準備・重複防止だけを維持し、送信成功や自動化完成とは呼ばない。
