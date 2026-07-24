"""
Phase 5 Verification Script.

Proves column-aware DataHub contract/assertion evaluation against live DataHub instance (http://localhost:8080):
- Scenario A (Drop lifetime_value): Assertion fct_user_orders_ltv_schema reported VIOLATED with clear rationale.
- Scenario B (Drop first_order_at): Exact same assertion reported UNAFFECTED, proving column precision.
"""

import logging
from blastradius.contracts import evaluate_contracts
from blastradius.resolver import resolve_entities_to_urns
from blastradius.datahub_client import DataHubRestGraphClient
from blastradius.models import ChangedEntity, ColumnChange, ChangeType
from blastradius.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_contracts")


def verify_contracts() -> None:
    logger.info("=== Phase 5 Column-Aware Contracts Verification ===")
    logger.info(f"Connecting DataHub SDK client to {config.datahub_gms_url}...")

    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)

    # Resolve target entity URN
    raw_entity = ChangedEntity(
        urn="",
        dataset_name="fct_user_orders",
        change_type=ChangeType.COLUMN_DROP,
    )
    resolved_entity = resolve_entities_to_urns([raw_entity], env="PROD", client=client)[0]
    print(f"Target Resolved URN: {resolved_entity.urn}")

    # SCENARIO A: Drop lifetime_value (Protected column by assertion)
    logger.info("\n--- Scenario A: Drop Protected Column 'lifetime_value' (Expect VIOLATED) ---")
    entity_a = ChangedEntity(
        urn=resolved_entity.urn,
        dataset_name="fct_user_orders",
        change_type=ChangeType.COLUMN_DROP,
        column_changes=[
            ColumnChange(
                column_name="lifetime_value",
                change_type=ChangeType.COLUMN_DROP,
                description="Dropped lifetime_value column"
            )
        ]
    )

    results_a = evaluate_contracts([entity_a], client=client)
    print(f"   --> Assertions Evaluated ({len(results_a)}):")
    for res in results_a:
        print(f"       - [{res.status}] Assertion: {res.assertion_urn}")
        print(f"         Protected Fields: {res.protected_fields}")
        print(f"         Violating Column: {res.violating_column}")
        print(f"         Reason: {res.description}")

    # Assertions for Scenario A
    assert len(results_a) >= 1, "Expected at least 1 assertion evaluated for Scenario A"
    assert results_a[0].status == "VIOLATED", f"Expected status VIOLATED, got {results_a[0].status}"
    assert results_a[0].violating_column == "lifetime_value", f"Expected violating column 'lifetime_value', got {results_a[0].violating_column}"

    # SCENARIO B: Drop first_order_at (Unprotected Column)
    logger.info("\n--- Scenario B: Drop Unprotected Column 'first_order_at' (Expect UNAFFECTED) ---")
    entity_b = ChangedEntity(
        urn=resolved_entity.urn,
        dataset_name="fct_user_orders",
        change_type=ChangeType.COLUMN_DROP,
        column_changes=[
            ColumnChange(
                column_name="first_order_at",
                change_type=ChangeType.COLUMN_DROP,
                description="Dropped first_order_at column"
            )
        ]
    )

    results_b = evaluate_contracts([entity_b], client=client)
    print(f"   --> Assertions Evaluated ({len(results_b)}):")
    for res in results_b:
        print(f"       - [{res.status}] Assertion: {res.assertion_urn}")
        print(f"         Protected Fields: {res.protected_fields}")
        print(f"         Violating Column: {res.violating_column}")
        print(f"         Reason: {res.description}")

    # Assertions for Scenario B
    assert len(results_b) >= 1, "Expected at least 1 assertion evaluated for Scenario B"
    assert results_b[0].status == "UNAFFECTED", f"Expected status UNAFFECTED, got {results_b[0].status}"
    assert results_b[0].violating_column is None, f"Expected None violating column, got {results_b[0].violating_column}"

    print("\nSUCCESS: Phase 5 Contracts verification passed 100%! Scenario A flagged VIOLATED; Scenario B left assertion UNAFFECTED, proving true column-level precision!")


if __name__ == "__main__":
    verify_contracts()
