"""STVV LAB: daily discovery opportunities, without automated replies or fake metrics."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

JST = timezone(timedelta(hours=9))
REPORT = Path("reports/discovery-latest.md")
SEARCHES = [
    ("STVV・シントトロイデン", "STVV OR シントトロイデン"),
    ("STVV日本人選手", "STVV 日本人"),
    ("試合・速報", "シントトロイデン 試合"),
    ("ベルギーリーグ", "ベルギーリーグ 日本人"),
    ("英語圏のSTVVファン", "Sint-Truiden OR STVV"),
]

def search_url(query):
    return "https://x.com/search?q=" + quote(query, safe="") + "&f=live"

def build(history, now):
    day = now.date().isoformat()
    posts = [p for p in history.get("publication_log", []) if isinstance(p, dict)]
    recent = posts[-7:]
    sourced = [p for p in recent if p.get("source")]
    lines = [
        "# STVV LAB｜発見されるための行動リスト",
        "",
        f"更新：{now:%Y-%m-%d %H:%M} JST",
        "",
        "## 1. 今日チェックするXの会話",
        "",
        "検索結果の新着投稿を開き、事実確認できる話題だけに参加してください。",
        "無差別返信・定型文の大量送信・自動フォローは行いません。",
        "",
    ]
    for title, query in SEARCHES:
        lines.append(f"- [{title}]({search_url(query)})")
    lines.extend([
        "",
        "## 2. 返信の基準（1日3〜5件を目安）",
        "",
        "- 相手の投稿に具体的に関連する情報を一つ加える",
        "- 試合結果・選手名・数字は必ず出典を確認する",
        "- 不明な事実を断定しない。宣伝リンクの貼り付けは原則しない",
        "- 意味のある返信ができなければ返信しない",
        "",
        "## 3. 今日の返信案（投稿内容に合わせて人が編集）",
        "",
        "- 試合結果の投稿：『この試合は［実際に確認した場面］が印象的でした。［確認した根拠］も興味深いですね。』",
        "- 日本人選手の投稿：『［選手名］の［確認したプレー］に注目しました。［具体的な理由］が大きいと思います。』",
        "- 戦術の投稿：『［該当シーン］では［確認した配置］がポイントに見えました。皆さんはどう見ましたか？』",
        "",
        "※角括弧は未記入の確認項目です。空欄のまま送信しないでください。",
        "",
        "## 4. 直近7投稿の発見可能性チェック",
        "",
        f"- 投稿履歴：{len(recent)}件",
        f"- 出典付き：{len(sourced)}件",
        f"- 出典なし：{len(recent)-len(sourced)}件",
        "- X側の表示回数・プロフィール閲覧・フォロー増はこのレポートでは取得していません",
        "",
        "## 5. 明日の改善ポイント",
        "",
        "- 出典付きの具体的な試合・選手の投稿を優先",
        "- 選手名・相手チーム名・試合名など検索される固有名詞を本文に含める",
        "- 反応の良かった投稿を確認し、次の分析テーマに反映",
        "",
    ])
    for p in sourced[-3:]:
        label = str(p.get("key", "投稿")).replace("|", "")
        lines.append(f"- 確認済み出典付き投稿：{label}")
    return "\n".join(lines) + "\n"

def main():
    history = json.loads(Path("posted.json").read_text(encoding="utf-8"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build(history, datetime.now(JST)), encoding="utf-8")
    print(f"Created {REPORT}")

if __name__ == "__main__":
    main()
