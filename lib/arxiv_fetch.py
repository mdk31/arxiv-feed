"""Fetch and parse arxiv category RSS feeds into a deduped list of new/cross papers."""
import re
import feedparser

RSS_URL_TEMPLATE = "https://rss.arxiv.org/rss/{category}"
ARXIV_ID_RE = re.compile(r"abs/([^/]+?)(?:v\d+)?$")
ANNOUNCE_TYPE_RE = re.compile(r"Announce Type:\s*([\w-]+)", re.IGNORECASE)


def _extract_arxiv_id(link):
    match = ARXIV_ID_RE.search(link)
    return match.group(1) if match else None


def _extract_announce_type(entry, summary):
    # feedparser normalizes the arxiv:announce_type namespaced element onto
    # the entry under a few possible attribute names depending on version.
    for key in ("arxiv_announce_type", "announce_type"):
        value = entry.get(key)
        if value:
            return value.lower()
    match = ANNOUNCE_TYPE_RE.search(summary)
    return match.group(1).lower() if match else None


def _extract_abstract(summary):
    marker = "Abstract:"
    idx = summary.find(marker)
    if idx == -1:
        return summary.strip()
    return summary[idx + len(marker):].strip()


def _entries_to_papers(entries, category):
    """Pure transform: feedparser entries -> filtered/deduped-ready paper dicts.

    Kept separate from network fetching so it can be unit tested against a
    local fixture without hitting the network.
    """
    papers = []
    for entry in entries:
        link = entry.get("link", "")
        arxiv_id = _extract_arxiv_id(link)
        if not arxiv_id:
            continue
        summary = entry.get("summary", "")
        announce_type = _extract_announce_type(entry, summary)
        if announce_type not in ("new", "cross"):
            continue
        papers.append({
            "arxiv_id": arxiv_id,
            "title": entry.get("title", "").strip(),
            "abstract": _extract_abstract(summary),
            "link": link,
            "authors": entry.get("author", ""),
            "category": category,
            "published": entry.get("published", ""),
        })
    return papers


def parse_feed_content(raw_content, category):
    """Parse already-fetched feed content (bytes/str) into paper dicts."""
    parsed = feedparser.parse(raw_content)
    if parsed.bozo and not parsed.entries:
        raise parsed.bozo_exception or RuntimeError("feed parse failed")
    return _entries_to_papers(parsed.entries, category)


def fetch_category(category, timeout=30):
    """Fetch one category's RSS feed, returning a list of paper dicts.

    Retries once on failure; raises on the second failure so the caller
    can log and skip this category without aborting the whole run.
    """
    url = RSS_URL_TEMPLATE.format(category=category)
    for attempt in range(2):
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                raise parsed.bozo_exception or RuntimeError("feed parse failed")
            return _entries_to_papers(parsed.entries, category)
        except Exception:  # noqa: BLE001 - single retry, then propagate
            if attempt == 1:
                raise


def fetch_all(categories):
    """Fetch all categories, dedupe by arxiv_id (cross-listed papers collapse
    to a single entry), and return (papers, failed_categories)."""
    seen = {}
    failed = []
    for category in categories:
        try:
            for paper in fetch_category(category):
                if paper["arxiv_id"] not in seen:
                    seen[paper["arxiv_id"]] = paper
        except Exception as exc:  # noqa: BLE001 - logged by caller
            failed.append((category, str(exc)))
    return list(seen.values()), failed
