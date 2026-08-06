import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.arxiv_fetch import (
    parse_feed_content,
    _extract_arxiv_id,
    _extract_announce_type,
    _extract_abstract,
)

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_cs_cl.xml")


class ExtractArxivIdTests(unittest.TestCase):
    def test_plain_link(self):
        self.assertEqual(_extract_arxiv_id("https://arxiv.org/abs/2607.05398"), "2607.05398")

    def test_no_match_returns_none(self):
        self.assertIsNone(_extract_arxiv_id("https://arxiv.org/list/cs.CL/recent"))


class ExtractAnnounceTypeTests(unittest.TestCase):
    def test_from_entry_attribute(self):
        entry = {"arxiv_announce_type": "New"}
        self.assertEqual(_extract_announce_type(entry, ""), "new")

    def test_from_summary_fallback(self):
        summary = "arXiv:2607.05398v1 Announce Type: cross\nAbstract: text"
        self.assertEqual(_extract_announce_type({}, summary), "cross")

    def test_missing_returns_none(self):
        self.assertIsNone(_extract_announce_type({}, "no marker here"))


class ExtractAbstractTests(unittest.TestCase):
    def test_strips_prefix(self):
        summary = "arXiv:2607.05398v1 Announce Type: new\nAbstract: the actual abstract text"
        self.assertEqual(_extract_abstract(summary), "the actual abstract text")

    def test_no_marker_returns_full_text(self):
        self.assertEqual(_extract_abstract("just some text"), "just some text")


class ParseFeedContentTests(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH, "rb") as f:
            self.raw_content = f.read()

    def test_filters_to_new_and_cross_only(self):
        papers = parse_feed_content(self.raw_content, "cs.CL")
        ids = {p["arxiv_id"] for p in papers}
        self.assertEqual(ids, {"2607.05398", "2607.05412"})

    def test_excludes_replace_and_replace_cross(self):
        papers = parse_feed_content(self.raw_content, "cs.CL")
        ids = {p["arxiv_id"] for p in papers}
        self.assertNotIn("2601.01234", ids)
        self.assertNotIn("2601.05678", ids)

    def test_paper_fields_populated(self):
        papers = parse_feed_content(self.raw_content, "cs.CL")
        paper = next(p for p in papers if p["arxiv_id"] == "2607.05398")
        self.assertEqual(paper["title"], "How Personas Can Influence Agents to Play Split or Steal")
        self.assertTrue(paper["abstract"].startswith("Personas are often employed"))
        self.assertEqual(paper["link"], "https://arxiv.org/abs/2607.05398")
        self.assertEqual(paper["category"], "cs.CL")
        self.assertIn("Carlos Leon", paper["authors"])

    def test_version_suffix_not_included_in_id(self):
        papers = parse_feed_content(self.raw_content, "cs.CL")
        for paper in papers:
            self.assertNotIn("v", paper["arxiv_id"].split(".")[-1])


if __name__ == "__main__":
    unittest.main()
