"""Live integration test: hits the real rss.arxiv.org feed.

Deliberately NOT named test_*.py so `unittest discover` (default pattern)
skips it and the regular unit test run stays network-free. Run explicitly:

    .venv/bin/python -m unittest tests.live_test_arxiv_fetch -v
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.arxiv_fetch import fetch_category

ARXIV_ID_SHAPE_RE = re.compile(r"^\d{4}\.\d{4,5}$")


class LiveFetchCategoryTests(unittest.TestCase):
    def test_fetch_cs_cl_returns_well_formed_papers(self):
        papers = fetch_category("cs.CL")

        self.assertIsInstance(papers, list)
        self.assertGreater(
            len(papers), 0,
            "expected at least one new/cross cs.CL paper today - "
            "if this genuinely fails on a quiet day, that's informative too",
        )

        for paper in papers:
            with self.subTest(arxiv_id=paper.get("arxiv_id")):
                self.assertRegex(paper["arxiv_id"], ARXIV_ID_SHAPE_RE)
                self.assertTrue(paper["title"])
                self.assertTrue(paper["abstract"])
                self.assertNotIn("Announce Type:", paper["abstract"])
                self.assertTrue(paper["link"].startswith("https://arxiv.org/abs/"))
                self.assertEqual(paper["category"], "cs.CL")


if __name__ == "__main__":
    unittest.main()
