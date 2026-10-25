# STVV LAB 投稿品質チェックの運用

## 本番接続と検証
`stvv_post.publish` は実際の送信本文を、pending保存とBuffer送信の前に検査する。
重大な問題は送信・履歴変更なしで停止し、文体の改善推奨だけでは停止しない。
通常投稿は既存7枠でのみ実行し、テストではBuffer送信と保存をモックに置き換える。

`text_metrics.x_length` を投稿候補選定と最終品質判定で共用する。
URLは23、日本語等の非ASCII文字は保守的に2で数える。厳密なXのUnicode/絵文字パーサーではない。
公開APIの上限280に加え、本番の送信直前は固定タグ込み270以下に制限する。

## テスト
- 全体: `python -m unittest discover -s tests -v`
- 品質点検: `python -m unittest -v test_quality_gate test_preflight_post tests.test_quality_integration tests.test_design_brief`
- 候補の報告: `python quality_gate.py --posts posts.json`
- 不正候補はsend/saveが呼ばれず履歴不変、正常候補はpending保存後に送信処理へ進む。
- 送信結果不明の場合はpendingを残し同じkeyの再送を止める。
- `tests/test_quality_rules.py` により単体ルールとpreflightも通常CIで実行する。

## 画像
画像は既存のreviewed manifest、本文完全一致、SHA256、寸法、復号、公開バイト照合を引き続き通す。
`design_brief.build_brief(source_url, reviewed_text, history)` は内蔵imagegen用の構図案を作る。
5つの方向性を公開履歴で均等に回し、直前の方向を避ける。pendingやスキップでは回さない。
出力は `brief_only` であり、画像生成成功・審査合格・ready登録ではない。
完成画像を内蔵imagegenで生成して目視確認し、manifestに任意の `art_direction` を記録する。
正式なsource/date/text/reviewed/sha256/dimensionsゲートは省略しない。
正確に対応するreadyカードのart_directionだけをpendingと公開履歴へ保存する。
課金APIは使用しない。自動視覚判定のみで事実の正確性や読みやすさを保証しない。

## 実動状態
既存のハイドゥク戦カードは2026-10-24の定期枠でBuffer受付とX表示まで確認済み。
今回の文字数修正後の実投稿、およびアメコミ方向性の定期公開は別途実測が必要。
新しい公式未投稿情報がない場合は画像を作らず投稿を見送る。
