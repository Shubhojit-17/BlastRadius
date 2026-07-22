"""
Resolver Verification Test Suite (FIX 1 & FIX 2).

Verifies resolver module robustness across 5 distinct test scenarios:
1. True Rename (AST source expression matching) -> 1 COLUMN_RENAME, 0 drops, 0 adds.
2. Drop + Unrelated Add (The Trap) -> 1 COLUMN_DROP, 1 COLUMN_ADD, 0 false renames.
3. Type Change -> 1 COLUMN_TYPE_CHANGE.
4. Full File Context-Line Parsing -> 13 context lines parsed cleanly.
5. Patch Hunk Fallback Compatibility -> original sample_pr_diff.patch passes.
"""

import os
import logging
from blastradius.resolver import parse_pr_diff, parse_sql_file_diff, resolve_entities_to_urns
from blastradius.datahub_client import DataHubRestGraphClient
from blastradius.models import ChangeType
from blastradius.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_resolver")


def load_fixture(filename: str) -> str:
    path = os.path.join("examples", filename)
    assert os.path.exists(path), f"Fixture not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_scenario_1_true_rename() -> None:
    logger.info("\n--- Scenario 1: True Rename (Source Expression Matching) ---")
    old_sql = load_fixture("fixture_rename_old.sql")
    new_sql = load_fixture("fixture_rename_new.sql")

    entity = parse_sql_file_diff(old_sql, new_sql, model_name="fct_user_orders")
    print(f"Changes found: {[c.description for c in entity.column_changes]}")

    renames = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_RENAME]
    drops = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_DROP]
    adds = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_ADD]

    assert len(renames) == 1, f"Expected 1 rename, found {len(renames)}"
    assert renames[0].old_name == "lifetime_value" and renames[0].new_name == "ltv"
    assert len(drops) == 0, f"Expected 0 drops, found {len(drops)}"
    assert len(adds) == 0, f"Expected 0 adds, found {len(adds)}"
    print("   --> PASS: True rename identified accurately without false drops/adds!")


def test_scenario_2_trap_drop_add() -> None:
    logger.info("\n--- Scenario 2: Drop + Unrelated Add (The Trap) ---")
    old_sql = load_fixture("fixture_trap_drop_add_old.sql")
    new_sql = load_fixture("fixture_trap_drop_add_new.sql")

    entity = parse_sql_file_diff(old_sql, new_sql, model_name="fct_user_orders")
    print(f"Changes found: {[c.description for c in entity.column_changes]}")

    renames = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_RENAME]
    drops = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_DROP]
    adds = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_ADD]

    assert len(renames) == 0, f"Expected 0 false renames, found {len(renames)}"
    assert len(drops) == 1 and drops[0].column_name == "lifetime_value", "Expected COLUMN_DROP on lifetime_value"
    assert len(adds) == 1 and adds[0].column_name == "created_by", "Expected COLUMN_ADD on created_by"
    print("   --> PASS: Trap avoided! Exactly 1 drop and 1 add reported without false rename!")


def test_scenario_3_type_change() -> None:
    logger.info("\n--- Scenario 3: Column Data Type Change ---")
    old_sql = load_fixture("fixture_type_change_old.sql")
    new_sql = load_fixture("fixture_type_change_new.sql")

    entity = parse_sql_file_diff(old_sql, new_sql, model_name="fct_user_orders")
    print(f"Changes found: {[c.description for c in entity.column_changes]}")

    type_changes = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_TYPE_CHANGE]
    assert len(type_changes) == 1, f"Expected 1 type change, found {len(type_changes)}"
    assert type_changes[0].old_type == "INT" and type_changes[0].new_type == "VARCHAR"
    print("   --> PASS: Data type cast modification detected successfully!")


def test_scenario_4_context_lines() -> None:
    logger.info("\n--- Scenario 4: Full File Parsing with 10+ Context Lines ---")
    old_sql = load_fixture("fixture_full_model_old.sql")
    new_sql = load_fixture("fixture_full_model_new.sql")

    file_contents = {"models/analytics/fct_user_orders.sql": (old_sql, new_sql)}
    changed_entities = parse_pr_diff(file_contents=file_contents)

    assert len(changed_entities) == 1
    entity = changed_entities[0]
    print(f"Changes found: {[c.description for c in entity.column_changes]}")

    drops = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_DROP]
    assert len(drops) == 1 and drops[0].column_name == "lifetime_value"
    print("   --> PASS: Full file with 13 context lines parsed cleanly!")


def test_scenario_5_fallback_patch() -> None:
    logger.info("\n--- Scenario 5: Patch Hunk Fallback Compatibility ---")
    patch_content = load_fixture("sample_pr_diff.patch")

    changed_entities = parse_pr_diff(diff_content=patch_content)
    assert len(changed_entities) == 1
    entity = changed_entities[0]

    drops = [c for c in entity.column_changes if c.change_type == ChangeType.COLUMN_DROP]
    assert len(drops) == 1 and drops[0].column_name == "lifetime_value"

    # Resolve entity URN via live DataHub client
    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)
    resolved_entities = resolve_entities_to_urns(changed_entities, env="PROD", client=client)
    assert "analytics.fct_user_orders" in resolved_entities[0].urn
    print(f"   --> Resolved URN: {resolved_entities[0].urn}")
    print("   --> PASS: Fallback patch parser operates backwards-compatibly!")


def verify_resolver_suite() -> None:
    logger.info("=== Resolver FIX 1 & FIX 2 Complete Verification Suite ===")
    test_scenario_1_true_rename()
    test_scenario_2_trap_drop_add()
    test_scenario_3_type_change()
    test_scenario_4_context_lines()
    test_scenario_5_fallback_patch()
    print("\nSUCCESS: All 5 resolver test scenarios passed 100%! FIX 1 and FIX 2 fully verified!")


if __name__ == "__main__":
    verify_resolver_suite()
