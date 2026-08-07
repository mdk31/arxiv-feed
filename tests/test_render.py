import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feedparser

from lib.render import render_feed, write_feed, _parse_pubdate


def make_item(arxiv_id, title="Title", authors="", published=""):
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": f"Abstract for {arxiv_id}",
        "link": f"https://arxiv.org/abs/{arxiv_id}",
        "authors": authors,
        "category": "cs.CL",
        "published": published,
        "judged_at": "2026-08-04T06:30:00",
        "reason": "on topic",
    }


class ParsePubdateTests(unittest.TestCase):
    def test_parses_rfc822_date(self):
        dt = _parse_pubdate("Wed, 08 Jul 2026 00:00:00 -0400")
        assert dt is not None
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 7)

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_pubdate(""))

    def test_garbage_returns_none(self):
        self.assertIsNone(_parse_pubdate("not a date"))


class RenderFeedTests(unittest.TestCase):
    def test_produces_parseable_rss(self):
        items = [make_item("2607.05398")]
        xml_bytes = render_feed(items, "Test Feed", "https://example.com/feed.xml", "desc")
        parsed = feedparser.parse(xml_bytes)
        self.assertEqual(parsed.bozo, 0)
        self.assertEqual(len(parsed.entries), 1)

    def test_empty_items_produces_valid_empty_feed(self):
        xml_bytes = render_feed([], "Test Feed", "https://example.com/feed.xml", "desc")
        parsed = feedparser.parse(xml_bytes)
        self.assertEqual(len(parsed.entries), 0)
        self.assertEqual(parsed.feed.title, "Test Feed")

    def test_preserves_caller_order_newest_first(self):
        items = [make_item("newer"), make_item("older")]
        xml_bytes = render_feed(items, "Test Feed", "https://example.com/feed.xml", "desc")
        parsed = feedparser.parse(xml_bytes)
        ids = [e.link.split("/")[-1] for e in parsed.entries]
        self.assertEqual(ids, ["newer", "older"])

    def test_authors_appear_as_dc_creator(self):
        items = [make_item("2607.05398", authors="Jane Doe, John Smith")]
        xml_bytes = render_feed(items, "Test Feed", "https://example.com/feed.xml", "desc")
        parsed = feedparser.parse(xml_bytes)
        self.assertEqual(parsed.entries[0].author, "Jane Doe, John Smith")

    def test_no_authors_omits_author_field(self):
        items = [make_item("2607.05398", authors="")]
        xml_bytes = render_feed(items, "Test Feed", "https://example.com/feed.xml", "desc")
        parsed = feedparser.parse(xml_bytes)
        self.assertFalse(hasattr(parsed.entries[0], "author"))

    def test_missing_published_omits_pubdate(self):
        items = [make_item("2607.05398", published="")]
        xml_bytes = render_feed(items, "Test Feed", "https://example.com/feed.xml", "desc")
        parsed = feedparser.parse(xml_bytes)
        self.assertFalse(hasattr(parsed.entries[0], "published"))

    def test_present_published_included(self):
        items = [make_item("2607.05398", published="Wed, 08 Jul 2026 00:00:00 -0400")]
        xml_bytes = render_feed(items, "Test Feed", "https://example.com/feed.xml", "desc")
        parsed = feedparser.parse(xml_bytes)
        self.assertTrue(hasattr(parsed.entries[0], "published"))


class WriteFeedTests(unittest.TestCase):
    def test_writes_file_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "feed.xml")
            write_feed([make_item("2607.05398")], "Test Feed", "https://example.com/feed.xml", "desc", output_path)
            self.assertTrue(os.path.exists(output_path))
            parsed = feedparser.parse(output_path)
            self.assertEqual(len(parsed.entries), 1)


if __name__ == "__main__":
    unittest.main()
