"""Git commit + push of the rendered feed file, from a working directory that's a git repo."""
import subprocess


def _run_git(repo_dir, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )


def has_remote(repo_dir):
    result = _run_git(repo_dir, "remote")
    return result.returncode == 0 and bool(result.stdout.strip())


def commit_and_push(repo_dir, file_path, commit_message):
    """Stage file_path (relative to repo_dir), commit if there's a diff, and
    push. Returns (success: bool, message: str) - never raises, so a single
    failed publish never crashes the run.
    """
    if not has_remote(repo_dir):
        return False, "no git remote configured, skipping publish"

    add_result = _run_git(repo_dir, "add", file_path)
    if add_result.returncode != 0:
        return False, f"git add failed: {add_result.stderr.strip()}"

    diff_result = _run_git(repo_dir, "diff", "--cached", "--quiet")
    if diff_result.returncode == 0:
        return True, "no changes to publish"

    commit_result = _run_git(repo_dir, "commit", "-m", commit_message)
    if commit_result.returncode != 0:
        return False, f"git commit failed: {commit_result.stderr.strip()}"

    push_result = _run_git(repo_dir, "push")
    if push_result.returncode != 0:
        return False, f"git push failed: {push_result.stderr.strip()}"

    return True, "published"
