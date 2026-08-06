import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.publish import has_remote, commit_and_push


def _result(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


class HasRemoteTests(unittest.TestCase):
    @patch("lib.publish.subprocess.run")
    def test_true_when_remote_listed(self, mock_run):
        mock_run.return_value = _result(returncode=0, stdout="origin\n")
        self.assertTrue(has_remote("/repo"))

    @patch("lib.publish.subprocess.run")
    def test_false_when_no_remotes(self, mock_run):
        mock_run.return_value = _result(returncode=0, stdout="")
        self.assertFalse(has_remote("/repo"))

    @patch("lib.publish.subprocess.run")
    def test_false_when_command_fails(self, mock_run):
        mock_run.return_value = _result(returncode=1, stderr="not a git repo")
        self.assertFalse(has_remote("/repo"))


class CommitAndPushTests(unittest.TestCase):
    @patch("lib.publish.subprocess.run")
    def test_no_remote_skips_publish(self, mock_run):
        mock_run.return_value = _result(returncode=0, stdout="")  # `git remote` empty
        success, message = commit_and_push("/repo", "feed.xml", "update")
        self.assertFalse(success)
        self.assertIn("no git remote", message)

    @patch("lib.publish.subprocess.run")
    def test_no_changes_returns_success_without_commit(self, mock_run):
        mock_run.side_effect = [
            _result(returncode=0, stdout="origin\n"),  # remote
            _result(returncode=0),                     # add
            _result(returncode=0),                     # diff --cached --quiet -> no diff
        ]
        success, message = commit_and_push("/repo", "feed.xml", "update")
        self.assertTrue(success)
        self.assertIn("no changes", message)
        self.assertEqual(mock_run.call_count, 3)

    @patch("lib.publish.subprocess.run")
    def test_full_success_path_commits_and_pushes(self, mock_run):
        mock_run.side_effect = [
            _result(returncode=0, stdout="origin\n"),  # remote
            _result(returncode=0),                     # add
            _result(returncode=1),                     # diff --cached --quiet -> has diff
            _result(returncode=0),                     # commit
            _result(returncode=0),                     # push
        ]
        success, message = commit_and_push("/repo", "feed.xml", "update")
        self.assertTrue(success)
        self.assertEqual(message, "published")
        self.assertEqual(mock_run.call_count, 5)

    @patch("lib.publish.subprocess.run")
    def test_add_failure_reported(self, mock_run):
        mock_run.side_effect = [
            _result(returncode=0, stdout="origin\n"),
            _result(returncode=1, stderr="add exploded"),
        ]
        success, message = commit_and_push("/repo", "feed.xml", "update")
        self.assertFalse(success)
        self.assertIn("git add failed", message)

    @patch("lib.publish.subprocess.run")
    def test_commit_failure_reported(self, mock_run):
        mock_run.side_effect = [
            _result(returncode=0, stdout="origin\n"),
            _result(returncode=0),
            _result(returncode=1),  # has diff
            _result(returncode=1, stderr="commit exploded"),
        ]
        success, message = commit_and_push("/repo", "feed.xml", "update")
        self.assertFalse(success)
        self.assertIn("git commit failed", message)

    @patch("lib.publish.subprocess.run")
    def test_push_failure_reported(self, mock_run):
        mock_run.side_effect = [
            _result(returncode=0, stdout="origin\n"),
            _result(returncode=0),
            _result(returncode=1),  # has diff
            _result(returncode=0),  # commit ok
            _result(returncode=1, stderr="push exploded"),
        ]
        success, message = commit_and_push("/repo", "feed.xml", "update")
        self.assertFalse(success)
        self.assertIn("git push failed", message)

    @patch("lib.publish.subprocess.run")
    def test_never_raises_on_failure(self, mock_run):
        mock_run.side_effect = [
            _result(returncode=0, stdout="origin\n"),
            _result(returncode=1, stderr="boom"),
        ]
        try:
            commit_and_push("/repo", "feed.xml", "update")
        except Exception as exc:  # noqa: BLE001
            self.fail(f"commit_and_push raised unexpectedly: {exc}")


if __name__ == "__main__":
    unittest.main()
