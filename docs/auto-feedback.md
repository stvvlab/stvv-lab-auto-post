# STVV LAB 自動フィードバック（レビュー用）

## 現状
この変更は **別ブランチにある試作品** です。main の既存自動投稿は変更していません。

- Buffer 投稿 ID を使ったメトリクス収集
- 統計が欠ける場合は採点せず、ゼロを補いません
- 直近21日・公開から48時間経過・20表示以上・10件以上を条件に相対評価
- 月曜日に `reports/latest.md` と週別レポートを生成
- 既存の手動評価は維持
- 投稿自体は実行しません

## 注意（公開前に必須）
Buffer の Metrics API は実験的仕様であり、**GraphQL フィールドと返却指標名を実 API で検証できていません**。
初回は workflow_dispatch で検証し、ログの `Buffer metrics unavailable` の有無、
`feedback.json` 内の `metrics` 内容を確認してください。

`feedback.json` で以下の3項目を true にしてから機能を有効化できます。
- auto_metrics_enabled
- auto_improvement_enabled
- weekly_report_enabled

**この段階ではすべて false のままにしています。**
本番へ反映する前に API レスポンスに合わせた修正、フォーマット検証、
重複・同時書き込みの検証が必要です。

自動評価は「内容の正確性」ではなく、数値に基づく相対比較のみを示します。
**現行 stvv_post.py は自動評価をまだ使いません。** 投稿改善へ接続するには
実績が取れた後に安全な候補スコア選択を実装してください。
