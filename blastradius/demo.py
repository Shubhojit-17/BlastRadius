"""
BlastRadius Zero-Setup Offline Demo CLI Entrypoint.

Runs the complete BlastRadius pipeline end-to-end using MockDataHubClient and recorded fixtures.
Operates 100% offline with zero infrastructure, zero Docker, zero DataHub Core, and zero API keys required.

Usage:
    python -m blastradius.demo
"""

import os
import sys
import logging
from blastradius.orchestrator import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("demo")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_demo() -> None:
    print("=" * 60)
    print("🚀 BlastRadius Zero-Setup Offline Demo")
    print("Running full pipeline using MockDataHubClient & Recorded Fixtures...")
    print("=" * 60)

    base_dir = os.path.dirname(__file__)
    fixtures_dir = os.path.join(base_dir, "..", "examples")

    old_sql_path = os.path.join(fixtures_dir, "fixture_full_model_old.sql")
    new_sql_path = os.path.join(fixtures_dir, "fixture_full_model_new.sql")

    if os.path.exists(old_sql_path) and os.path.exists(new_sql_path):
        with open(old_sql_path, "r") as f:
            base_sql = f.read()
        with open(new_sql_path, "r") as f:
            head_sql = f.read()
    else:
        base_sql = "SELECT user_id, first_order_at, lifetime_value FROM analytics.fct_user_orders;"
        head_sql = "SELECT user_id, first_order_at FROM analytics.fct_user_orders;"

    report, exit_code = run_pipeline(base_sql, head_sql, use_mock=True, pr_number=42, commit_sha="demo123")

    print("\n" + "=" * 60)
    print("GENERATED PR COMMENT (ZERO-SETUP OFFLINE DEMO OUTPUT):")
    print("=" * 60)
    print(report.summary_markdown)
    print("=" * 60)
    print(f"Verdict Exit Code: {exit_code} (1 = HIGH RISK, 0 = OK)")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
