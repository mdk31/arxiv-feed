import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.classifier import build_messages, parse_verdict, classify


class BuildMessagesTests(unittest.TestCase):
    def test_returns_system_and_user_roles(self):
        messages = build_messages("profile text", "Some Title", "Some abstract")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")

    def test_profile_injected_into_system_prompt(self):
        messages = build_messages("only interested in cats", "T", "A")
        self.assertIn("only interested in cats", messages[0]["content"])

    def test_title_and_abstract_in_user_message(self):
        messages = build_messages("profile", "My Title", "My abstract text")
        self.assertIn("My Title", messages[1]["content"])
        self.assertIn("My abstract text", messages[1]["content"])


class ParseVerdictTests(unittest.TestCase):
    def test_parses_plain_json(self):
        relevant, reason = parse_verdict('{"relevant": true, "reason": "on topic"}')
        self.assertTrue(relevant)
        self.assertEqual(reason, "on topic")

    def test_parses_false_verdict(self):
        relevant, reason = parse_verdict('{"relevant": false, "reason": "off topic"}')
        self.assertFalse(relevant)

    def test_strips_markdown_code_fence(self):
        raw = '```json\n{"relevant": true, "reason": "x"}\n```'
        relevant, reason = parse_verdict(raw)
        self.assertTrue(relevant)

    def test_missing_reason_defaults_empty(self):
        relevant, reason = parse_verdict('{"relevant": true}')
        self.assertEqual(reason, "")

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            parse_verdict("not json at all")

    def test_missing_relevant_key_raises(self):
        with self.assertRaises(KeyError):
            parse_verdict('{"reason": "no relevant key"}')

    def test_non_bool_relevant_raises(self):
        with self.assertRaises(ValueError):
            parse_verdict('{"relevant": "yes", "reason": "x"}')


class ClassifyTests(unittest.TestCase):
    def _mock_response(self, content):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"message": {"content": content}}
        return mock_resp

    @patch("lib.classifier.requests.post")
    def test_success_on_first_attempt(self, mock_post):
        mock_post.return_value = self._mock_response('{"relevant": true, "reason": "yes"}')
        relevant, reason = classify("profile", "title", "abstract", "http://localhost:11434", "model")
        self.assertTrue(relevant)
        self.assertEqual(reason, "yes")
        self.assertEqual(mock_post.call_count, 1)

    @patch("lib.classifier.requests.post")
    def test_retries_once_then_succeeds(self, mock_post):
        mock_post.side_effect = [
            RuntimeError("network blip"),
            self._mock_response('{"relevant": false, "reason": "no"}'),
        ]
        relevant, reason = classify("profile", "title", "abstract", "http://localhost:11434", "model")
        self.assertFalse(relevant)
        self.assertEqual(mock_post.call_count, 2)

    @patch("lib.classifier.requests.post")
    def test_raises_after_two_failures(self, mock_post):
        mock_post.side_effect = RuntimeError("still down")
        with self.assertRaises(RuntimeError):
            classify("profile", "title", "abstract", "http://localhost:11434", "model")
        self.assertEqual(mock_post.call_count, 2)

    @patch("lib.classifier.requests.post")
    def test_malformed_json_counts_as_failure_and_retries(self, mock_post):
        mock_post.side_effect = [
            self._mock_response("not valid json"),
            self._mock_response('{"relevant": true, "reason": "recovered"}'),
        ]
        relevant, reason = classify("profile", "title", "abstract", "http://localhost:11434", "model")
        self.assertTrue(relevant)
        self.assertEqual(mock_post.call_count, 2)

    @patch("lib.classifier.requests.post")
    def test_request_payload_shape(self, mock_post):
        mock_post.return_value = self._mock_response('{"relevant": true, "reason": "x"}')
        classify("my profile", "my title", "my abstract", "http://localhost:11434", "qwen2.5:3b-instruct")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://localhost:11434/api/chat")
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "qwen2.5:3b-instruct")
        self.assertEqual(payload["format"], "json")
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertFalse(payload["stream"])


if __name__ == "__main__":
    unittest.main()
