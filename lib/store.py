"""Local state: a permanent seen-IDs dedup ledger and a rolling published-items list."""
import json
import os


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_seen(seen_ids, arxiv_id):
    return arxiv_id in seen_ids


def record_seen(seen_ids, arxiv_id, relevant, judged_at):
    """Mutates and returns seen_ids with this arxiv_id's judgement recorded.

    Never pruned - this is the permanent dedup ledger so a paper already
    judged (relevant or not) is never re-judged by the LLM.
    """
    seen_ids[arxiv_id] = {"judged_at": judged_at, "relevant": relevant}
    return seen_ids


def add_relevant_item(published_items, item, window_size):
    """Pure function: prepend a newly-relevant item, sort newest-first by
    judged_at, and truncate to window_size. Returns a new list.
    """
    updated = published_items + [item]
    updated.sort(key=lambda i: i["judged_at"], reverse=True)
    return updated[:window_size]
