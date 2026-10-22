# 投稿後の補足・分析リプ

ユーザーの希望は、投稿した内容の補足・分析を、その元ポストへのリプに追記すること。
反応数のレポートや、別の新規ポストを増やすことではない。

## 現在の状態（2026-10-22確認）

未実装。`auto_feedback.py` は指標収集であり、補足リプを投稿する機能ではない。
現行の Buffer GraphQL API は公開済み X ポストへの返信を受け付けない。
`metadata.twitter.thread` は新しい親ポストを含むスレッドの一括作成用で、既存ポストへの追記に流用しない。

- https://support.buffer.com/articles/using-buffers-api-GtIYIQilz5
- https://developers.buffer.com/types/TwitterPostMetadataInput.html
- https://developers.buffer.com/examples/create-threaded-post.html

`send` と `publish` に `reply_to` を指定した場合は、送信・pending保存前に
`blocked_unsupported_reply` として停止する。通常ポストへのフォールバックは禁止。
既存7枠の送信経路・重複判定・画像照合は変更しない。

## 実装を完了するために必要なこと

1. 既存ポストに返信できる送信手段を確保する。追加課金APIは使わない。
   Buffer API対応待ち、または認証済みX/Buffer画面での操作が候補。
2. Buffer IDと公開済みXのURL/IDを対応付ける。Buffer受付のみを公開確認扱いにしない。
3. 元ポスト・過去リプ・確認済み一次資料を比較し、未掲載の補足がある場合だけ候補を作る。
   推測と事実を区別し、資料にない戦術や数値を補完しない。新しい材料がなければ見送る。
4. 返信先の本人アカウントを確認し、親ID＋補足内容で重複防止し、送信前pendingを保存する。
5. Xで親子関係と表示を確認してから公開済みにする。送信結果不明時は再送しない。

このガードの実装・テスト成功は、補足リプ機能の完成や実投稿成功を意味しない。
