# STVV LAB 投稿品質チェックの運用

## 現状
- `quality_gate.py`: 投稿候補全体の問題を報告。
- `preflight_post.py`: JSONの単一投稿に対する公開可否を判定。
- `test_quality_gate.py` と `test_preflight_post.py`: 判定のテスト（計16件）。
- `.github/workflows/quality-audit.yml`: Actionsの手動実行と関連ファイルのPR更新で実行。

**注意：これらは本番のBuffer送信処理に未接続です。**

## GitHubでの検証
GitHubの Actions → STVV LAB Quality Audit → Run workflow → Run workflow
を押し、`audit` ジョブのテスト結果と候補投稿の警告を確認してください。

## ローカルでの検証
```bash
python -m unittest -v test_quality_gate.py test_preflight_post.py
python quality_gate.py --posts posts.json
python quality_gate.py --posts posts.json --enforce-critical
printf '%s\n' '{"type":"news","text":"試合速報","source_url":"https://example.com/match"}' | python preflight_post.py
```

## 本番連携の条件
1. 実際にBufferへ送信するスクリプトを特定する。
2. 送信直前に、**実際に送信する本文と出典を含む**JSONを`preflight_post.py`で確認する。
3. 終了コードが0以外ならBuffer送信を中止してログに記録する。
4. 同一投稿の重複送信防止と、送信後の実績記録を維持する。
5. ステージングで検証してから本番に反映する。

**制限：出典URLの存在確認や情報の真偽、画像品質までを保証するものではありません。**
