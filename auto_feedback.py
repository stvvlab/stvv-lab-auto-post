"""STVV LAB: collect experimental Buffer metrics; never publish.
Missing metrics are not zeros. API failures do not stop posting.
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

JST = timezone(timedelta(hours=9))
FEEDBACK = Path("feedback.json")
HISTORY = Path("posted.json")
REPORTS = Path("reports")
BUFFER_API = "https://api.buffer.com"
MAX_CALLS = 30
WINDOW_DAYS = 21
MIN_AGE_HOURS = 48
MIN_IMPRESSIONS = 20
MIN_COMPARABLE_POSTS = 10

def parse_date(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def metric_query(post_id, session, key):
    query = """query { post(input: { id: %s }) {
      id status metricsUpdatedAt metrics { type name value unit }
    } }""" % json.dumps(post_id)
    response = session.post(
        BUFFER_API,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        json={"query": query},
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise ValueError("Buffer GraphQL rejected the metrics query")
    post = (payload.get("data") or {}).get("post")
    if not isinstance(post, dict):
        raise ValueError("Buffer returned no post")
    return post

def unpack_metrics(post):
    values = {}
    for item in post.get("metrics") or []:
        if not isinstance(item, dict) or item.get("unit") not in {"count", "percentage"}:
            continue
        metric_type = item.get("type")
        if not isinstance(metric_type, str) or not metric_type:
            continue
        raw = item.get("value")
        if isinstance(raw, bool):
            continue
        try:
            number = float(raw)
        except (ValueError, TypeError):
            continue
        if math.isfinite(number) and number >= 0:
            values[metric_type] = number
    return values

def collect_metrics(feedback, history, now, session, key):
    indexed = {
        item["post_key"]: item
        for item in feedback.get("metrics", [])
        if isinstance(item, dict) and isinstance(item.get("post_key"), str)
    }
    candidates = []
    for post in history.get("publication_log", []):
        if not isinstance(post, dict):
            continue
        post_key, post_id = post.get("key"), post.get("buffer_id")
        submitted = parse_date(post.get("submitted_at"))
        if not isinstance(post_key, str) or not isinstance(post_id, str) or not submitted:
            continue
        age = now - submitted
        if not (timedelta(hours=MIN_AGE_HOURS) <= age <= timedelta(days=WINDOW_DAYS)):
            continue
        previous = indexed.get(post_key)
        last_check = parse_date(previous.get("checked_at")) if previous else None
        if last_check and now - last_check < timedelta(hours=23):
            continue
        candidates.append((last_check or datetime.min.replace(tzinfo=JST), post))
    candidates.sort(key=lambda entry: entry[0])
    total = min(len(candidates), MAX_CALLS)
    successes = 0
    collection_error = None
    for _, item in candidates[:MAX_CALLS]:
        try:
            result = metric_query(item["buffer_id"], session, key)
        except (requests.RequestException, ValueError) as error:
            collection_error = type(error).__name__
            print("Buffer metrics unavailable; stopping this run:", collection_error)
            break
        indexed[item["key"]] = {
            "post_key": item["key"],
            "slot": item.get("slot"),
            "buffer_id": item["buffer_id"],
            "submitted_at": item.get("submitted_at"),
            "checked_at": now.isoformat(),
            "metrics_updated_at": result.get("metricsUpdatedAt"),
            "status": result.get("status"),
            "values": unpack_metrics(result) if result.get("status") == "sent" else {},
        }
        successes += 1
    feedback["metrics"] = sorted(indexed.values(), key=lambda p: p["post_key"])
    feedback["last_collection"] = {
        "checked_at": now.isoformat(),
        "eligible": total,
        "checked": successes,
        "status": "unavailable" if collection_error else ("ok" if total else "no_eligible_posts"),
        "error_class": collection_error,
    }
    print(f"Checked {successes}/{total} eligible Buffer posts")

def engagement_rate(entry):
    if entry.get("status") != "sent" or not entry.get("metrics_updated_at"):
        return None
    numbers = entry.get("values") or {}
    views = numbers.get("impressions")
    if not isinstance(views, (int, float)) or views < MIN_IMPRESSIONS:
        return None
    reactions = numbers.get("reactions", numbers.get("likes"))
    if not any(x in numbers for x in ("reactions", "likes", "comments", "reposts", "shares")):
        return None
    total = sum((n or 0) for n in (
        reactions, numbers.get("comments"), numbers.get("reposts", numbers.get("shares"))
    ))
    return total / views

def automatic_ratings(feedback, now):
    recent = []
    for snapshot in feedback.get("metrics", []):
        submission = parse_date(snapshot.get("submitted_at"))
        if not submission or not (
            timedelta(hours=MIN_AGE_HOURS) <= now - submission <= timedelta(days=WINDOW_DAYS)
        ):
            continue
        rate = engagement_rate(snapshot)
        if rate is not None:
            recent.append((snapshot, rate))
    if len(recent) < MIN_COMPARABLE_POSTS:
        print(f"Not enough comparable posts ({len(recent)}/{MIN_COMPARABLE_POSTS}); no auto ratings")
        return []
    sorted_rates = sorted(rate for _, rate in recent)
    result = []
    for item, rate in recent:
        less = sum(x < rate for x in sorted_rates)
        ties = sum(x == rate for x in sorted_rates)
        percentile = (less + (ties - 1) / 2) / (len(sorted_rates) - 1)
        rating = min(5, 1 + int(percentile * 5))
        result.append({
            "post_key": item["post_key"],
            "slot": item.get("slot"),
            "rating": rating,
            "engagement_rate": round(rate, 6),
            "basis": "relative_engagement_rate_21d",
            "updated_at": now.isoformat(),
        })
    return sorted(result, key=lambda item: item["post_key"])

def weekly_report(feedback, now):
    if now.weekday() != 0:
        return
    week = now.isocalendar()
    REPORTS.mkdir(exist_ok=True)
    reviews = feedback.get("automatic_feedback", [])
    metrics = feedback.get("metrics", [])
    lines = [
        f"# STVV LAB 週間フィードバック（{week.year}-W{week.week:02d}）",
        "",
        f"作成日時（JST）：{now:%Y-%m-%d %H:%M}",
        f"Buffer実績の保存件数：{len(metrics)}",
        f"比較可能な自動評価：{len(reviews)}件",
        "",
        "※ Bufferの数値は試験提供・更新遅延があります。表示回数がない投稿は採点していません。",
        "※ 自動評価は21日間のエンゲージメント率を相対比較した目安で、内容の正確性は評価していません。",
        "※ 手動の評価を優先し、推測による数値補完は行いません。",
        "",
    ]
    if reviews:
        lines.append("## 相対評価の高い投稿")
        for item in sorted(reviews, key=lambda x: (-x["rating"], -x["engagement_rate"]))[:5]:
            lines.append(f"- \x60{item['post_key']}\x60：{item['rating']}/5、反応率 {item['engagement_rate'] * 100:.2f}%")
        lines.extend(["", "## 見直し候補"])
        for item in sorted(reviews, key=lambda x: (x["rating"], x["engagement_rate"]))[:5]:
            lines.append(f"- \x60{item['post_key']}\x60：{item['rating']}/5、反応率 {item['engagement_rate'] * 100:.2f}%")
    else:
        lines.append("比較可能な実績が不足しているため、順位付けは保留しています。")
    lines.append("")
    report = "\n".join(lines)
    (REPORTS / "weekly-latest.md").write_text(report, encoding="utf-8")
    (REPORTS / f"weekly-{week.year}-W{week.week:02d}.md").write_text(report, encoding="utf-8")


def daily_report(feedback, history, now):
    """Publish a readable status even before enough posts qualify for a rating."""
    REPORTS.mkdir(exist_ok=True)
    day = (now - timedelta(days=1)).date()
    day_posts = []
    for item in history.get("publication_log", []):
        if not isinstance(item, dict):
            continue
        submitted = parse_date(item.get("submitted_at"))
        if submitted and submitted.astimezone(JST).date() == day:
            day_posts.append(item)

    total = len(day_posts)
    with_image = sum(bool(p.get("image_url")) for p in day_posts)
    with_source = sum(bool(p.get("source")) for p in day_posts)
    metrics = [p for p in feedback.get("metrics", []) if isinstance(p, dict)]
    with_views = [
        p for p in metrics
        if p.get("status") == "sent"
        and p.get("metrics_updated_at")
        and isinstance((p.get("values") or {}).get("impressions"), (int, float))
    ]
    collection = feedback.get("last_collection", {})
    ratings = feedback.get("automatic_feedback", [])
    lines = [
        f"# STVV LAB 日次フィードバック（対象：{day}）",
        "",
        f"作成日時（JST）：{now:%Y-%m-%d %H:%M}",
        "",
        "## 前日の投稿状況",
        f"- 投稿登録：{total}件",
        f"- Buffer送信時に画像URLを指定：{with_image}件 / {total}件",
        f"- 出典付きの試合・ニュース投稿：{with_source}件 / {total}件",
        f"- 汎用テーマ投稿：{total - with_source}件 / {total}件",
        "",
        "※ 画像URLの指定は、Xへの画像掲載成功を保証するものではありません。",
        "※ 出典がない一般論を、実際のSTVVの試合分析として採点しません。",
        "",
        "## 実測データの収集",
        f"- Buffer実績取得済み：{len(metrics)}投稿",
        f"- 表示回数を取得済み：{len(with_views)}投稿",
        f"- 比較条件を満たした相対評価：{len(ratings)}件",
        f"- 最新取得結果：{collection.get('status', '未実行')}",
        f"- 最新取得処理：{collection.get('checked', '未実行')}件",
        "",
    ]
    if with_views:
        lines.append("### 最近取得できた表示回数")
        for item in sorted(with_views, key=lambda p: p.get("checked_at") or "", reverse=True)[:5]:
            number = item["values"]["impressions"]
            lines.append(f"- {item.get('post_key', 'unknown')}: {number:g}表示")
        lines.append("")
    else:
        lines.extend(["表示回数の実測値はまだ取得できていません。未取得は0回として扱いません。", ""])
    # Measured impression performance, never substituting zero for missing values.
    if with_views:
        ranked = sorted(with_views, key=lambda p: p["values"]["impressions"], reverse=True)
        views_total = sum(p["values"]["impressions"] for p in with_views)
        lines.extend([
            "## インプレッション重視の効果測定",
            f"- 実測表示回数合計：{views_total:g}回（{len(with_views)}投稿）",
            f"- 1投稿平均：{views_total / len(with_views):.2f}回",
            f"- 20表示以上：{sum(p['values']['impressions'] >= 20 for p in with_views)}投稿",
            "",
            "### 表示回数TOP5",
        ])
        for item in ranked[:5]:
            lines.append(f"- {item.get('post_key', 'unknown')}：{item['values']['impressions']:g}回")
        lines.extend(["", "### 投稿枠別の平均表示回数"])
        grouped = {}
        for item in with_views:
            grouped.setdefault(item.get("slot") or "unknown", []).append(item["values"]["impressions"])
        for slot, values in sorted(grouped.items(), key=lambda x: -sum(x[1]) / len(x[1])):
            lines.append(f"- {slot}：{sum(values) / len(values):.2f}回（{len(values)}投稿）")
        lines.extend(["", "※ 投稿後の経過時間や収集時点が異なるため、比較は暫定値です。", ""])
    else:
        lines.extend(["## インプレッション重視の効果測定", "実測表示回数は未取得です。", ""])
    lines.append("## 評価の利用状況")
    lines.append("- 各形式につき評価済み投稿が3件以上集まるまで、形式の優劣は判断しません。")
    lines.append("- 現行の定期投稿では汎用文の候補選択を停止しており、収集した評価を投稿形式の自動選択には反映していません。")
    lines.append("- この処理は指標の収集とレポート作成のみです。投稿済みポストへの補足・分析リプは送信しません（送信機能は未実装）。")
    lines.append("- 画像の良し悪しは本文の反応だけでは判定できないため、画像デザインの自動変更は保留します。")
    lines.append("")
    lines.append("## 次の改善事項")
    if total == 0:
        lines.append("- 前日の投稿登録がありません。GitHub Actionsの実行履歴とBufferを照合してください。")
    else:
        if with_image < total:
            lines.append("- 画像なし投稿があります。画像の生成・公開先・Buffer画像添付を確認してください。")
        if with_source < total:
            lines.append("- 一般論の投稿があります。最新の試合・選手・公式情報に基づく具体的な投稿を優先してください。")
        if with_image == total and with_source == total:
            lines.append("- 投稿画像と出典の指定はできています。X側の掲載状態と実際の反応を確認してください。")
    if len(ratings) == 0:
        lines.append("- 十分な反応データがないため、投稿の優劣を断定しません。")
    lines.append("")
    report = "\n".join(lines)
    (REPORTS / "latest.md").write_text(report, encoding="utf-8")
    (REPORTS / f"daily-{day}.md").write_text(report, encoding="utf-8")


def run(now=None, session=None):
    now = now or datetime.now(JST)
    session = session or requests.Session()
    data = read_json(FEEDBACK)
    history = read_json(HISTORY)
    settings = data.get("settings", {})
    if not settings.get("feedback_enabled", False):
        print("Feedback disabled")
        return
    if settings.get("auto_metrics_enabled", False):
        key = os.getenv("BUFFER_API_KEY", "")
        if key:
            collect_metrics(data, history, now, session, key)
        else:
            print("BUFFER_API_KEY missing; metrics collection skipped")
    if settings.get("auto_improvement_enabled", False):
        data["automatic_feedback"] = automatic_ratings(data, now)
    if settings.get("weekly_report_enabled", False):
        weekly_report(data, now)
    if settings.get("daily_report_enabled", True):
        daily_report(data, history, now)
    write_json(FEEDBACK, data)

if __name__ == "__main__":
    run()
