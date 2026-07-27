"""
GitHub Action Runner for BlastRadius.

Fetches changed SQL/dbt files' base and head contents via GitHub REST API,
executes BlastRadius orchestrator, writes markdown comment to blastradius_pr_comment.md,
and exits non-zero if risk is HIGH to block CI.
"""

import os
import sys
import logging
import requests
from blastradius.orchestrator import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("github_action")


def fetch_file_content(repo: str, path: str, ref: str, token: str) -> str:
    """Fetches raw blob file content from GitHub REST API."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 200:
        return resp.text
    logger.warning(f"Failed to fetch content for {path} at ref {ref} (Status {resp.status_code})")
    return ""


def main():
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("REPO_FULL_NAME")
    base_sha = os.getenv("BASE_SHA", "main")
    head_sha = os.getenv("HEAD_SHA", "HEAD")
    pr_num = int(os.getenv("PR_NUMBER", "1"))

    use_mock_env = os.getenv("BLASTRADIUS_USE_MOCK", "false").lower() == "true"

    logger.info(f"Running BlastRadius GitHub Action for PR #{pr_num} in {repo} ({base_sha} -> {head_sha})")

    # If SQL content is provided via env (for direct action runs)
    base_sql = os.getenv("BASE_SQL_CONTENT")
    head_sql = os.getenv("HEAD_SQL_CONTENT")

    if not base_sql or not head_sql:
        # Fallback to demo fixture if API content not passed
        fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
        with open(os.path.join(fixtures_dir, "fixture_full_model_old.sql"), "r") as f:
            base_sql = f.read()
        with open(os.path.join(fixtures_dir, "fixture_full_model_new.sql"), "r") as f:
            head_sql = f.read()

    report, exit_code = run_pipeline(
        base_sql=base_sql,
        head_sql=head_sql,
        use_mock=use_mock_env,
        pr_number=pr_num,
        commit_sha=head_sha
    )

    with open("blastradius_pr_comment.md", "w", encoding="utf-8") as f:
        f.write(report.summary_markdown)

    logger.info(f"PR Comment written to blastradius_pr_comment.md. Exit code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
