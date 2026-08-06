import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.store import load_json, save_json, is_seen, record_seen, add_relevant_item


class LoadSaveJsonTests(unittest.TestCase):
    def test_load_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "does_not_exist.json")
            self.assertEqual(load_json(path, {"x": 1}), {"x": 1})

    def test_save_then_load_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "data.json")
            data = {"a": [1, 2, 3], "b": "text"}
            save_json(path, data)
            self.assertEqual(load_json(path, None), data)

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b", "c", "data.json")
            save_json(path, {})
            self.assertTrue(os.path.exists(path))


class SeenIdsTests(unittest.TestCase):
    def test_is_seen_false_for_unknown_id(self):
        self.assertFalse(is_seen({}, "2607.05398"))

    def test_record_seen_marks_id(self):
        seen = {}
        record_seen(seen, "2607.05398", relevant=True, judged_at="2026-08-04T06:30:00")
        self.assertTrue(is_seen(seen, "2607.05398"))
        self.assertEqual(seen["2607.05398"]["relevant"], True)
        self.assertEqual(seen["2607.05398"]["judged_at"], "2026-08-04T06:30:00")

    def test_record_seen_returns_same_dict_mutated(self):
        seen = {}
        result = record_seen(seen, "2607.05398", relevant=False, judged_at="2026-08-04T06:30:00")
        self.assertIs(result, seen)

    def test_not_relevant_still_recorded_as_seen(self):
        seen = {}
        record_seen(seen, "2607.05398", relevant=False, judged_at="2026-08-04T06:30:00")
        self.assertTrue(is_seen(seen, "2607.05398"))
        self.assertFalse(seen["2607.05398"]["relevant"])


class AddRelevantItemTests(unittest.TestCase):
    def _item(self, arxiv_id, judged_at):
        return {"arxiv_id": arxiv_id, "title": arxiv_id, "judged_at": judged_at}

    def test_prepends_new_item(self):
        existing = [self._item("a", "2026-08-01T00:00:00")]
        updated = add_relevant_item(existing, self._item("b", "2026-08-02T00:00:00"), window_size=10)
        self.assertEqual([i["arxiv_id"] for i in updated], ["b", "a"])

    def test_does_not_mutate_input_list(self):
        existing = [self._item("a", "2026-08-01T00:00:00")]
        add_relevant_item(existing, self._item("b", "2026-08-02T00:00:00"), window_size=10)
        self.assertEqual(len(existing), 1)

    def test_sorts_newest_first_regardless_of_input_order(self):
        existing = [
            self._item("old", "2026-08-01T00:00:00"),
            self._item("mid", "2026-08-03T00:00:00"),
        ]
        updated = add_relevant_item(existing, self._item("new", "2026-08-02T00:00:00"), window_size=10)
        self.assertEqual([i["arxiv_id"] for i in updated], ["mid", "new", "old"])

    def test_truncates_to_window_size(self):
        existing = [self._item(str(i), f"2026-08-{i:02d}T00:00:00") for i in range(1, 6)]
        updated = add_relevant_item(existing, self._item("new", "2026-08-10T00:00:00"), window_size=3)
        self.assertEqual(len(updated), 3)
        self.assertEqual(updated[0]["arxiv_id"], "new")

    def test_window_size_larger_than_items_keeps_all(self):
        existing = [self._item("a", "2026-08-01T00:00:00")]
        updated = add_relevant_item(existing, self._item("b", "2026-08-02T00:00:00"), window_size=150)
        self.assertEqual(len(updated), 2)


if __name__ == "__main__":
    unittest.main()
