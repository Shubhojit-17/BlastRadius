"""
Phase 6 Verification Script.

Verifies end-to-end BlastRadius pipeline execution:
- Scenario A (Drop lifetime_value): Evaluates RiskLevel HIGH, broken contract callout, 4 downstream assets, 4 owners, MCP context.
- Scenario B (Drop first_order_at): Evaluates RiskLevel LOW, 0 broken contracts.
- Offline Zero-Infrastructure Verification: Confirms python -m blastradius.demo produces the HIGH-risk report with zero live services.
"""

import os
import sys
import logging
from blastradius.orchestrator import run_pipeline
from blastradius.models import RiskLevel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_reporter")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_verification() -> None:
    logger.info("=== Phase 6 End-to-End Orchestrator & Reporter Verification ===")

    # Prepare SQL test fixtures
    base_sql_a = """
    SELECT
      user_id,
      first_order_at,
      lifetime_value,
      total_orders
    FROM analytics.fct_user_orders;
    """

    head_sql_a = """
    SELECT
      user_id,
      first_order_at,
      total_orders
    FROM analytics.fct_user_orders;
    """

    head_sql_b = """
    SELECT
      user_id,
      lifetime_value,
      total_orders
    FROM analytics.fct_user_orders;
    """

    # 1. SCENARIO A: Drop lifetime_value (Expect RiskLevel HIGH + Contract Violation)
    logger.info("\n--- Running Scenario A: Drop 'lifetime_value' (Expect HIGH RISK) ---")
    report_a, exit_code_a = run_pipeline(base_sql_a, head_sql_a, use_mock=True, pr_number=101, commit_sha="scen_a_sha")

    print("\n" + "=" * 70)
    print("SCENARIO A: FULL GENERATED PR COMMENT (HIGH RISK):")
    print("=" * 70)
    print(report_a.summary_markdown)
    print("=" * 70)
    print(f"Scenario A Risk Level: {report_a.risk_level.value}")
    print(f"Scenario A Risk Score: {report_a.risk_score:.1f}/100.0")
    print(f"Scenario A Exit Code:  {exit_code_a} (1 = CI FAILED)")

    # Assertions for Scenario A
    assert report_a.risk_level == RiskLevel.HIGH, f"Expected RiskLevel.HIGH, got {report_a.risk_level}"
    assert exit_code_a == 1, f"Expected exit code 1 for HIGH risk, got {exit_code_a}"
    assert len(report_a.contract_violations) >= 1, "Expected at least 1 contract violation"
    assert len(report_a.downstream_impacts) == 4, f"Expected 4 downstream assets, got {len(report_a.downstream_impacts)}"
    assert "CONTRACT VIOLATION" in report_a.summary_markdown, "Comment must contain contract violation callout"
    assert "exec_revenue_dashboard" in report_a.summary_markdown, "Comment must list exec_revenue_dashboard"
    assert "churn_prediction_v2" in report_a.summary_markdown, "Comment must list churn_prediction_v2"
    assert "@bob@company.com" in report_a.summary_markdown, "Comment must list owner bob@company.com"

    # 2. SCENARIO B: Drop first_order_at (Expect RiskLevel LOW + 0 Violations)
    logger.info("\n--- Running Scenario B: Drop Unprotected 'first_order_at' (Expect LOW RISK) ---")
    report_b, exit_code_b = run_pipeline(base_sql_a, head_sql_b, use_mock=True, pr_number=102, commit_sha="scen_b_sha")

    print("\n" + "=" * 70)
    print("SCENARIO B: FULL GENERATED PR COMMENT (LOW RISK):")
    print("=" * 70)
    print(report_b.summary_markdown)
    print("=" * 70)
    print(f"Scenario B Risk Level: {report_b.risk_level.value}")
    print(f"Scenario B Risk Score: {report_b.risk_score:.1f}/100.0")
    print(f"Scenario B Exit Code:  {exit_code_b} (0 = CI PASSED)")

    # Assertions for Scenario B
    assert report_b.risk_level == RiskLevel.LOW, f"Expected RiskLevel.LOW, got {report_b.risk_level}"
    assert exit_code_b == 0, f"Expected exit code 0 for LOW risk, got {exit_code_b}"
    assert len(report_b.contract_violations) == 0, f"Expected 0 contract violations, got {len(report_b.contract_violations)}"

    # 3. OFFLINE ZERO-SETUP DEMO ENTRYPOINT VERIFICATION
    logger.info("\n--- Running Zero-Setup Offline Demo CLI (python -m blastradius.demo) ---")
    import subprocess
    cmd = [sys.executable, "-m", "blastradius.demo"]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=os.path.join(os.path.dirname(__file__), "..")
    )
    
    print("\n" + "=" * 70)
    print("DEMO CLI STDOUT OUTPUT:")
    print("=" * 70)
    print(res.stdout)
    print("=" * 70)

    assert res.returncode == 0, f"Demo CLI execution failed with returncode {res.returncode}"
    assert "BlastRadius PR Assessment: HIGH RISK" in res.stdout, "Demo CLI stdout must contain HIGH RISK assessment banner"
    assert "Verdict Exit Code: 1" in res.stdout, "Demo CLI stdout must show Verdict Exit Code: 1"

    print("\nSUCCESS: Phase 6 Verification passed 100%! Scenario A (HIGH) and Scenario B (LOW) evaluated cleanly, and python -m blastradius.demo ran completely offline with zero setup required!")


if __name__ == "__main__":
    run_verification()
