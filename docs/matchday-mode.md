# 試合日モード（段階1：審査済み候補の優先順位）

通常の投稿枠（JST 08:00 選手 / 18:00 ニュース / 23:00 振り返り）は変更しない。
試合日専用の新しい cron、即時投稿、引用リポスト、画像の無人生成は**未実装**。

## 実装したこと

- 既存の予約候補のうち、**試合日専用として明示承認済み**の投稿を同じ枠の通常候補より先に検討する。
- 対象は `editorial/imagegen_cards.json` に登録され、`reviewed=true`、`status=ready`、既存の出典・重複・画像等の審査を通るカードだけ。
- `editorial_purpose` の `kind/phase` が `fixture/matchday`、`fixture/lineup`、`match/lineup`、`match/final`、`match/recap`、`result/final`、`result/recap` のいずれかで、空でない `event_id` を持ち、`publish_due_jst` が**対象の枠と完全一致**すること。
- 対象候補がないときは従来の候補順に戻る。未承認素材を自動生成したり、試合日を推測したりしない。
- 実行レポートの候補には `matchday_priority` を記録する。これは優先順位であり、投稿成功やX表示確認の証拠ではない。

## 審査済みカードの例（概念）

```json
{
  "reviewed": true,
  "status": "ready",
  "slots": ["news"],
  "publish_due_jst": "2026-11-08T18:00:00+09:00",
  "editorial_purpose": {
    "kind": "fixture",
    "phase": "matchday",
    "event_id": "officially-confirmed-fixture-id"
  }
}
```

この例だけでは投稿できない。本文、公式出典、審査済み画像または明示承認済みテキスト、本文SHA256等の既存必須項目も必要。

## 今後の別課題

1. 公式日程から試合日とキックオフ時刻を取得・照合し、特別版候補の制作を支援する。
2. スタメン発表・試合終了の検知と、公式情報が揃った後の候補生成を設計する。
3. 本文・画像の承認と、Buffer送信後のX実表示確認を維持する。

**注意**：この段階1をマージしても、スタメン発表直後や試合終了直後の自動投稿は始まらない。既存予約や手動投稿済みの投稿を移動・再送・削除しない。
