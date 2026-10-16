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
    for _, item in candidates[:MAX_CALLS]:
        try:
            result = metric_query(item["buffer_id"], session, key)
        except (requests.RequestException, ValueError) as error:
            print("Buffer metrics unavailable; stopping this run:", type(error).__name__)
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
    (REPORTS / "latest.md").write_text(report, encoding="utf-8")
    (REPORTS / f"weekly-{week.year}-W{week.week:02d}.md").write_text(report, encoding="utf-8")

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
    write_json(FEEDBACK, data)

if __name__ == "__main__":
    run()
