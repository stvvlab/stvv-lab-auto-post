"""Prepare safe supplemental replies without pretending a transport exists."""
import hashlib
import re
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

JST_OFFSET = "+09:00"
OWN_HANDLE = "stvvlabo"
X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
OFFICIAL_HOSTS = {"stvv.jp", "www.stvv.com", "stvv.com", "www.uefa.com", "uefa.com"}
TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "xclid"}
PARENT_REGISTRY = Path(__file__).resolve().parent / 'editorial/supplemental_replies.json'


class ReplyValidationError(ValueError):
    pass


def read_parent_registry():
    try:
        data = json.loads(PARENT_REGISTRY.read_text(encoding='utf-8'))
        if not isinstance(data.get('parents'), list):
            raise ValueError('invalid parent registry')
        return data['parents']
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise ReplyValidationError('verified parent registry unavailable') from error


def _now_iso():
    return datetime.now().astimezone().isoformat()


def canonical_source(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise ReplyValidationError("supplement source must be an approved official HTTPS URL")
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)]
    return urlunparse(("https", parsed.netloc.lower(), parsed.path.rstrip("/") + "/",
                       "", urlencode(query), ""))


def parent_post_id(parent_url):
    parsed = urlparse(parent_url)
    if parsed.scheme != "https" or parsed.hostname not in X_HOSTS:
        raise ReplyValidationError("parent must be an X URL")
    match = re.fullmatch(rf"/{OWN_HANDLE}/status/([0-9]{{1,19}})/?", parsed.path, re.I)
    if not match:
        raise ReplyValidationError("parent must be a verified @stvvlabo status URL")
    return match.group(1)


def reply_key(parent_id, text, source_url):
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
    material = f"{parent_id}\n{normalized}\n{canonical_source(source_url)}"
    return "supplement_" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_candidate(candidate, history):
    if candidate.get("reviewed") is not True or candidate.get("status") != "ready":
        raise ReplyValidationError("reply is not reviewed and ready")
    parent_id = parent_post_id(candidate.get("parent_x_url", ""))
    if candidate.get("parent_post_id") != parent_id:
        raise ReplyValidationError("parent post ID does not match parent URL")
    parent_key = candidate.get("parent_key")
    parents = [item for item in history.get("publication_log", [])
               if item.get("key") == parent_key]
    if len(parents) != 1:
        raise ReplyValidationError("parent is not uniquely present in publication history")
    # An arbitrary own-account status must not be paired with an unrelated
    # historical key. Bind the observed X ID to exact durable parent evidence.
    matches = [p for p in read_parent_registry()
               if isinstance(p, dict) and p.get('parent_key') == parent_key]
    if len(matches) != 1:
        raise ReplyValidationError('parent mapping is missing or ambiguous')
    mapping, published = matches[0], parents[0]
    if (mapping.get('verified') is not True or mapping.get('owner') != OWN_HANDLE
            or mapping.get('parent_post_id') != parent_id
            or mapping.get('parent_x_url') != candidate.get('parent_x_url')
            or parent_post_id(mapping.get('parent_x_url', '')) != parent_id
            or not published.get('text') or not published.get('buffer_id')
            or mapping.get('parent_text') != published.get('text')
            or mapping.get('buffer_id') != published.get('buffer_id')
            or canonical_source(mapping.get('source_url', '')) != canonical_source(published.get('source', ''))):
        raise ReplyValidationError('parent mapping does not match the verified publication')
    text = candidate.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ReplyValidationError("reply text is empty")
    source = canonical_source(candidate.get("source_url", ""))
    if candidate.get("source_url") not in text and source not in text:
        raise ReplyValidationError("official source URL must be visible in reply text")
    expected = reply_key(parent_id, text, source)
    supplied = candidate.get("key")
    if supplied is not None and supplied != expected:
        raise ReplyValidationError("reply key does not match parent, text and source")
    checked = deepcopy(candidate)
    checked["key"] = expected
    checked["source_url"] = source
    return checked


def stage_pending(history, candidate, persist):
    """Persist a reviewed reply before any future transport call."""
    checked = validate_candidate(candidate, history)
    key = checked["key"]
    history.setdefault("pending_replies", {})
    history.setdefault("used_reply_keys", [])
    history.setdefault("reply_publication_log", [])
    if (key in history["pending_replies"] or key in history["used_reply_keys"]
            or any(item.get("key") == key for item in history["reply_publication_log"])):
        return None
    history["pending_replies"][key] = {
        "key": key,
        "parent_key": checked["parent_key"],
        "parent_post_id": checked["parent_post_id"],
        "parent_x_url": checked["parent_x_url"],
        "text": checked["text"],
        "source_url": checked["source_url"],
        "state": "pending_before_send",
        "created_at": _now_iso(),
    }
    persist(history)
    return key


def mark_transport_unknown(history, key, detail, persist):
    pending = history.get("pending_replies", {}).get(key)
    if not pending:
        raise ReplyValidationError("reply is not pending")
    pending["state"] = "transport_result_unknown"
    pending["detail"] = str(detail)
    pending["updated_at"] = _now_iso()
    persist(history)


def mark_x_verified(history, key, reply_x_url, parent_post_id_value, persist):
    pending = history.get("pending_replies", {}).get(key)
    if not pending:
        raise ReplyValidationError("reply is not pending")
    reply_id = parent_post_id(reply_x_url)
    if reply_id == pending["parent_post_id"]:
        raise ReplyValidationError("reply URL cannot equal the parent URL")
    if str(parent_post_id_value) != pending["parent_post_id"]:
        raise ReplyValidationError("verified X relationship does not match the parent")
    record = dict(pending)
    record.update({
        "state": "published_and_x_relationship_verified",
        "reply_x_url": reply_x_url,
        "verified_at": _now_iso(),
    })
    history.setdefault("reply_publication_log", []).append(record)
    history.setdefault("used_reply_keys", []).append(key)
    del history["pending_replies"][key]
    persist(history)


def require_reply_transport(transport=None):
    if transport is None:
        raise RuntimeError(
            "blocked_no_reply_transport: no free authenticated transport can append "
            "to a published X post; do not create a standalone post"
        )
    return transport
