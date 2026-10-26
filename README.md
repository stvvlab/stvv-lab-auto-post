# STVV LAB

公式情報の収集、編集候補の検討、審査済み画像の定期配信を行うリポジトリです。
画像・本文の準備と、Xへの送信は別の段階です。

## 本番の流れ

1. `official_sources.py`：日本公式の一般・試合・UEFA一覧を取得・解析。
2. `preparation_inventory.py`：未投稿の新しい出典を収集。
3. `editorial_research.py`：掲載済み記事の未使用記述を検討用下書きにする。
4. ChatGPT内蔵imagegenで画像を作成し、本文・事実・画像を目視審査。
5. 画像と`editorial/imagegen_cards.json`を同じコミットで登録。
6. `stvv_post.py`が既存7枠で審査済み候補を選び、チェック後にBufferへ送信。

投稿枠（JST）：08:00／10:30／12:30／15:30／18:00／21:00／23:00。
情報・画像が不足する枠は見送ります。枠数は投稿数の保証ではありません。

## コードの役割

| 分類 | ファイル | 責務 |
| --- | --- | --- |
| 本番入口 | `stvv_post.py` | 枠の選択、候補の組み立て、pending保存、Buffer送信、履歴更新 |
| 取得 | `official_sources.py` | 公式一覧の取得、見出し・日付・対象記事の解析。送信しない |
| 準備 | `preparation_inventory.py`, `editorial_research.py`, `design_brief.py` | 新出典・未使用記述・構図の候補。審査や画像生成の代用ではない |
| 本番の安全確認 | `quality_gate.py`, `content_guard.py`, `editorial_novelty.py`, `text_metrics.py` | 出典・文字数・重複・限定的な新事実の検査 |
| 審査済み画像 | `prepared_media.py` | 本文との完全一致、公式本文、画像SHA・寸法・公開バイトの確認 |
| 計測・評価 | `auto_feedback.py`, `add_feedback.py` | 評価の収集・登録。補足リプの送信機能ではない |
| 補足リプ | `supplemental_replies.py` | 安全基盤のみ。送信経路は未接続 |
| 別系統 | `stvv_database/` | 試合データベースの同期。通常のX投稿とは別 |
| テスト | `tests/test_*.py` | 自動テストの正規配置。ルートのテストと取込用中継ファイルは廃止 |

`stvv_post.articles`、`scan_articles`、`parse_articles`などの既存呼出しは互換維持しています。
投稿本体にはまだ送信・履歴・試合文生成が同居しており、分割は段階的に進めます。

## Actionsの区分

| 用途 | ワークフロー | 外部への影響 |
| --- | --- | --- |
| 通常の本番投稿 | `main.yml` | 既存7枠でのみBufferへ送信 |
| 候補収集 | `discovery-brief.yml` | 証拠・候補レポートを保存。投稿しない |
| 品質・動作検証 | `quality-audit.yml`, `auto-feedback-tests.yml`, `visual-tests.yml` | テスト・監査・プレビュー。実投稿と区別する |
| 評価の運用 | `auto-feedback.yml`, `feedback.yml` | 評価・レポートを書き込む |
| DB同期 | `database-sync.yml` | スプレッドシート同期。X投稿ではない |
| 手動調査 | `runner-test.yml`, `buffer-metrics-probe.yml` | 個別の診断用。通常の公開経路ではない |
| 旧画像の検証 | `publish-cards.yml` | 旧方式の画像ファイルを作成・保存。現在の審査済みmanifestの代用にしない |
| 過去の公開実験 | `single-card-pilot.yml` | **実送信する処理を含む。通常運用で実行しない** |

旧方式の`generate_image.py`、`generate_social_cards.py`、`single_card.py`、
`publish_single_card.py`、プレビュー用の`content_card.py`等は、既存の参照・テストのため残しています。
審査済みmanifestが有効な本番処理から、これらへ勝手に戻すことはありません。
`editorial/first_verified_card.json`の更新やpilot再実行を通常投稿の起動に使いません。

## 一度まとめて確認する

リポジトリのルートで実行します。

```sh
python -m pip install requests beautifulsoup4 pillow
bash scripts/install-card-font.sh
python -m unittest discover -s tests -v
```

フォントを既に用意している環境では、インストールの代わりに
`STVV_CARD_FONT`へそのフォントのパスを指定できます。
テストログ内の送信成功表示はモックの場合があり、本番投稿の証拠にはなりません。
確認目的で本番送信スクリプトやpilotを起動しないでください。

## 設定・成果物・運用資料

- `editorial/`：審査済みmanifest、確認済み事実、編集用の設定。
- `generated/`：コミットする完成画像。未審査・過去の画像も含むため、存在だけで送信しない。
- `posted.json`：公開履歴とpending。手作業で消して再送を促さない。
- `reports/`：実測結果・候補・検証証拠。レポート更新だけで送信完了とはしない。
- [画像の準備・配信](docs/imagegen-delivery.md)
- [補足リプの制約](docs/supplemental-replies.md)
- [データベース同期](docs/database-sync.md)
- [自動フィードバック](docs/auto-feedback.md)

有料画像APIへは切り替えません。送信結果不明時はpendingを保持し、再送しません。
