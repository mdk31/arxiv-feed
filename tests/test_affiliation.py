import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import affiliation

INSTITUTIONS = {
    "Meta": {
        "aliases": [
            "Meta AI",
            "Meta FAIR",
            {"text": "FAIR", "case_sensitive": True},
            {"text": "Meta", "not_followed_by": ["-", " Learning"]},
        ],
        "domains": ["meta.com", "fb.com"],
    },
    "Stanford University": {"aliases": ["Stanford"], "domains": ["stanford.edu"]},
    "MIT": {"aliases": ["MIT", "Massachusetts Institute of Technology"], "domains": ["mit.edu", "csail.mit.edu"]},
    "Purdue University": {
        "aliases": ["Purdue University", {"text": "Purdue", "not_followed_by": [" Pharma"]}],
        "domains": ["purdue.edu"],
    },
}


class ExtractHeaderTextTests(unittest.TestCase):
    def test_truncates_at_abstract(self):
        text = "Title\nAuthor, Some Univ\nAbstract\nWe use GPT-4 from OpenAI."
        self.assertNotIn("OpenAI", affiliation.extract_header_text(text))

    def test_case_insensitive_abstract_marker(self):
        text = "Title\nAuthor\nABSTRACT\nMentions Meta here."
        self.assertNotIn("Meta", affiliation.extract_header_text(text))

    def test_no_abstract_marker_returns_full_text(self):
        text = "Title\nAuthor, Some Univ, no heading marker present here"
        self.assertEqual(affiliation.extract_header_text(text), text)


class MatchInstitutionsTests(unittest.TestCase):
    def test_matches_alias_in_header(self):
        text = "Some Paper\nJane Doe\nStanford University\njane@cs.stanford.edu"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), ["Stanford University"])

    def test_bare_meta_hyphenated_title_does_not_false_positive(self):
        text = "Meta-Learning for Robotics\nJane Doe, Some Univ\njane@example.edu"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])

    def test_bare_meta_learning_spaced_title_does_not_false_positive(self):
        text = "A Meta Learning Approach\nJane Doe, Some Univ\njane@example.edu"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])

    def test_bare_meta_as_real_affiliation_matches(self):
        text = "Some Paper\nJane Doe\nMeta\njane@meta.com"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), ["Meta"])

    def test_fair_lowercase_word_does_not_match(self):
        text = "A Fair Comparison of Methods\nJane Doe, Some Univ\njane@example.edu"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])

    def test_fair_uppercase_matches(self):
        text = "Jane Doe\nFAIR, Meta\njane@meta.com"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), ["Meta"])

    def test_purdue_pharma_does_not_false_positive(self):
        text = "A Study of Opioid Policy\nJane Doe, Some Univ\nSupported by Purdue Pharma funding."
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])

    def test_purdue_university_matches(self):
        text = "Jane Doe\nDepartment of Statistics, Purdue University"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), ["Purdue University"])

    def test_email_domain_matches_even_without_name_text(self):
        text = "Some Paper\nJane Doe\nMeta\njane@meta.com"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), ["Meta"])

    def test_subdomain_email_matches(self):
        text = "Some Paper\nJane Doe\nMIT CSAIL\njane@csail.mit.edu"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), ["MIT"])

    def test_mit_word_boundary_does_not_match_inside_other_words(self):
        text = "A New Method to Admit Uncertainty and Commit to Robust Limits\nJane Doe, Some Univ\njane@example.edu"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])

    def test_mit_does_not_match_inside_surname(self):
        text = "Jane Smith, Some Univ\njane@example.edu\nSafeCommit: A New Method"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])

    def test_no_match_returns_empty_list(self):
        text = "Some Paper\nJane Doe\nRandom University\njane@random.edu"
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])

    def test_does_not_match_mention_in_abstract_body(self):
        text = "Some Paper\nJane Doe\nYork University\njane@yorku.ca\nAbstract\nWe compare GPT-4 from OpenAI and Meta's Llama."
        self.assertEqual(affiliation.match_institutions(text, INSTITUTIONS), [])


class NameHelperTests(unittest.TestCase):
    def test_normalize_name_lowercases_and_collapses_whitespace(self):
        self.assertEqual(affiliation.normalize_name("  Jane   Doe "), "jane doe")

    def test_split_authors_splits_on_comma(self):
        self.assertEqual(affiliation.split_authors("Jane Doe, John Smith"), ["Jane Doe", "John Smith"])

    def test_split_authors_empty_string(self):
        self.assertEqual(affiliation.split_authors(""), [])


class LedgerTests(unittest.TestCase):
    def test_check_ledger_finds_known_author(self):
        ledger = {"jane doe": {"name": "Jane Doe", "institutions": ["Stanford University"], "seen_on": ["1234.5678"]}}
        authors, institutions = affiliation.check_ledger("Jane Doe, John Smith", ledger)
        self.assertEqual(authors, ["Jane Doe"])
        self.assertEqual(institutions, ["Stanford University"])

    def test_check_ledger_no_match_returns_empty(self):
        authors, institutions = affiliation.check_ledger("Jane Doe", {})
        self.assertEqual(authors, [])
        self.assertEqual(institutions, [])

    def test_update_ledger_adds_new_author(self):
        ledger = {}
        affiliation.update_ledger(ledger, "Jane Doe, John Smith", ["Stanford University"], "1234.5678")
        self.assertIn("jane doe", ledger)
        self.assertIn("john smith", ledger)
        self.assertEqual(ledger["jane doe"]["institutions"], ["Stanford University"])
        self.assertEqual(ledger["jane doe"]["seen_on"], ["1234.5678"])

    def test_update_ledger_no_institutions_is_noop(self):
        ledger = {}
        affiliation.update_ledger(ledger, "Jane Doe", [], "1234.5678")
        self.assertEqual(ledger, {})

    def test_update_ledger_accumulates_institutions_across_papers(self):
        ledger = {}
        affiliation.update_ledger(ledger, "Jane Doe", ["Stanford University"], "1111.1111")
        affiliation.update_ledger(ledger, "Jane Doe", ["Meta"], "2222.2222")
        self.assertEqual(set(ledger["jane doe"]["institutions"]), {"Stanford University", "Meta"})
        self.assertEqual(ledger["jane doe"]["seen_on"], ["1111.1111", "2222.2222"])

    def test_save_then_load_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "ledger.json")
            ledger = {"jane doe": {"name": "Jane Doe", "institutions": ["MIT"], "seen_on": ["1234.5678"]}}
            affiliation.save_researcher_ledger(path, ledger)
            loaded = affiliation.load_researcher_ledger(path)
            self.assertEqual(loaded, ledger)

    def test_load_missing_file_returns_empty_dict(self):
        self.assertEqual(affiliation.load_researcher_ledger("/nonexistent/path/ledger.json"), {})


class LoadInstitutionsTests(unittest.TestCase):
    def test_loads_and_flattens_sections(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                "academic:\n"
                "  Test Univ:\n"
                "    aliases: [Test Univ]\n"
                "    domains: [test.edu]\n"
                "industry:\n"
                "  Test Co:\n"
                "    aliases: [Test Co]\n"
                "    domains: [testco.com]\n"
            )
            path = f.name
        try:
            institutions = affiliation.load_institutions(path)
            self.assertEqual(set(institutions.keys()), {"Test Univ", "Test Co"})
            self.assertEqual(institutions["Test Univ"]["aliases"], ["Test Univ"])
            self.assertEqual(institutions["Test Co"]["domains"], ["testco.com"])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
