"""Render the rolling list of relevant papers into an RSS 2.0 feed."""
from email.utils import parsedate_to_datetime

from feedgen.feed import FeedGenerator


def _parse_pubdate(published):
    if not published:
        return None
    try:
        return parsedate_to_datetime(published)
    except (TypeError, ValueError):
        return None


def render_feed(items, feed_title, feed_link, feed_description):
    """items: list of paper dicts (as produced by store.add_relevant_item),
    already ordered newest-first. Returns RSS 2.0 XML as bytes.
    """
    fg = FeedGenerator()
    fg.load_extension("dc")
    fg.title(feed_title)
    fg.link(href=feed_link, rel="self")
    fg.description(feed_description)

    for item in items:
        # order="append" preserves our caller-provided (newest-first) order;
        # feedgen's default "prepend" would reverse it.
        fe = fg.add_entry(order="append")
        fe.id(item["link"])
        fe.title(item["title"])
        fe.link(href=item["link"])
        fe.description(item.get("abstract", ""))
        # feedgen's author() only renders in RSS given a valid email, which
        # arxiv doesn't provide - use dc:creator instead, same as arxiv's
        # own feed, so readers pick it up as the item's real byline.
        if item.get("authors"):
            fe.dc.dc_creator(item["authors"])
        pubdate = _parse_pubdate(item.get("published"))
        if pubdate:
            fe.pubDate(pubdate)

    return fg.rss_str(pretty=True)


def write_feed(items, feed_title, feed_link, feed_description, output_path):
    xml_bytes = render_feed(items, feed_title, feed_link, feed_description)
    with open(output_path, "wb") as f:
        f.write(xml_bytes)
