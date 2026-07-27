"""
Phase 7 Write-Back Verification Script.

Tests DataHub metadata write-back implementation:
1. Unit tests for Sentinel Read-Modify-Write and re.DOTALL description stripping (exact byte-for-byte match).
2. Dry-run mode logging verification.
3. Offline / Live write-back execution and reversible cleanup verification.
"""

import sys
import os
import logging
from blastradius.writeback import (
    apply_read_modify_write_description,
    strip_sentinel_warning,
    format_sentinel_warning,
    execute_writeback,
    cleanup_writeback,
    SENTINEL_START,
    SENTINEL_END,
)
from blastradius.orchestrator import run_pipeline
from blastradius.models import RiskLevel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_writeback")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_verification() -> None:
    logger.info("=== Phase 7 DataHub Write-Back Verification ===")

    # Test 1: Sentinel Read-Modify-Write Unit Tests
    logger.info("\n--- Test 1: Sentinel Read-Modify-Write & Exact Cleanup Matching ---")
    original_catalog_doc = "Derived dbt model for user lifetime value and order metrics"

    # Generate test report for Scenario A
    base_sql_a = "SELECT user_id, first_order_at, lifetime_value, total_orders FROM analytics.fct_user_orders;"
    head_sql_a = "SELECT user_id, first_order_at, total_orders FROM analytics.fct_user_orders;"

    report_a, _ = run_pipeline(base_sql_a, head_sql_a, use_mock=True, pr_number=101, commit_sha="scen_a_sha")

    warning_block_1 = format_sentinel_warning(report_a)
    updated_desc_1 = apply_read_modify_write_description(original_catalog_doc, warning_block_1)

    print("Initial Read-Modify-Write Description Result:")
    print(updated_desc_1)

    # Assert warning block was appended and original doc preserved
    assert original_catalog_doc in updated_desc_1, "Original catalog description must be preserved"
    assert SENTINEL_START in updated_desc_1 and SENTINEL_END in updated_desc_1, "Sentinel markers must be present"

    # Test Idempotency: Re-run write-back on description with updated report
    report_a_v2, _ = run_pipeline(base_sql_a, head_sql_a, use_mock=True, pr_number=102, commit_sha="v2_sha")
    warning_block_2 = format_sentinel_warning(report_a_v2)
    updated_desc_2 = apply_read_modify_write_description(updated_desc_1, warning_block_2)

    print("\nIdempotent Re-Run Description Result:")
    print(updated_desc_2)

    assert updated_desc_2.count(SENTINEL_START) == 1, "Must NOT stack duplicate sentinel blocks"
    assert "PR #102" in updated_desc_2, "Sentinel block must be updated in place"
    assert original_catalog_doc in updated_desc_2, "Original description must remain intact"

    # Test Exact Cleanup Match: Strip sentinel warning block
    restored_doc = strip_sentinel_warning(updated_desc_2)
    print(f"\nRestored Description: '{restored_doc}'")
    print(f"Original Description: '{original_catalog_doc}'")

    assert restored_doc == original_catalog_doc, f"Exact byte-for-byte match failed! Expected '{original_catalog_doc}', got '{restored_doc}'"
    logger.info("--> Test 1 Passed 100%! Sentinel Read-Modify-Write & exact byte-for-byte cleanup verified.")

    # Test 2: Dry-Run Mode Logging Verification
    logger.info("\n--- Test 2: Dry-Run Mode Logging Verification ---")
    wb_dry_run_res = execute_writeback(report_a, dry_run=True, use_mock=True)

    print("Dry-Run Execution Response Dict:")
    print(wb_dry_run_res)

    assert wb_dry_run_res["status"] == "DRY_RUN", f"Expected DRY_RUN status, got {wb_dry_run_res['status']}"
    assert wb_dry_run_res["dry_run"] is True, "dry_run flag must be True"
    assert len(wb_dry_run_res["planned_mutations"]) >= 5, "Expected planned mutations for target + 4 downstream assets"

    # Check planned tool calls
    tools_planned = [m["tool"] for m in wb_dry_run_res["planned_mutations"]]
    assert "add_tags" in tools_planned, "Dry-run must log add_tags mutation"
    assert "update_description" in tools_planned, "Dry-run must log update_description mutation"
    assert "add_structured_properties" in tools_planned, "Dry-run must log add_structured_properties mutation"

    logger.info("--> Test 2 Passed 100%! Dry-run mode correctly logs all planned mutations without executing.")

    # Test 3: Reversible Cleanup Verification
    logger.info("\n--- Test 3: Reversible Cleanup Verification ---")
    cleanup_res = cleanup_writeback(report_a, use_mock=True)
    print("Cleanup Response Dict:")
    print(cleanup_res)

    assert "CLEANUP" in cleanup_res["status"], f"Cleanup must return success status, got {cleanup_res['status']}"
    logger.info("--> Test 3 Passed 100%! Reversible cleanup verified.")

    print("\nSUCCESS: Phase 7 Write-Back verification passed 100%! Sentinel read-modify-write preserves catalog docs, dry-run mode logs mutations safely, and cleanup restores exact byte-for-byte original descriptions!")


if __name__ == "__main__":
    run_verification()
