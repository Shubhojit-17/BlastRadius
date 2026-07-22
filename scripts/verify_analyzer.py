"""
Phase 4 Verification Script.

Proves column-level blast radius precision against the live DataHub instance (http://localhost:8080):
- Scenario A (Drop lifetime_value): returns all 4 downstream assets (chart, 2nd-degree dashboard, ML feature, 2nd-degree model) and owners.
- Scenario B (Drop first_order_at - The Proof): returns 0 downstream assets (empty list), demonstrating true column-level precision over table-level fanout.
"""

import logging
from blastradius.analyzer import analyze_impact
from blastradius.resolver import resolve_entities_to_urns
from blastradius.datahub_client import DataHubRestGraphClient
from blastradius.models import ChangedEntity, ColumnChange, ChangeType
from blastradius.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_analyzer")


def verify_analyzer() -> None:
    logger.info("=== Phase 4 Column-Aware Analyzer Verification ===")
    logger.info(f"Connecting to DataHub GMS at {config.datahub_gms_url}...")

    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)

    # Resolve target entity URN
    raw_entity = ChangedEntity(
        urn="",
        dataset_name="fct_user_orders",
        change_type=ChangeType.COLUMN_DROP,
    )
    resolved_entity = resolve_entities_to_urns([raw_entity], env="PROD", client=client)[0]
    print(f"Target Resolved URN: {resolved_entity.urn}")

    # SCENARIO A: Drop lifetime_value (Has 4 downstream dependents across 2 hops)
    logger.info("\n--- Scenario A: Drop 'lifetime_value' (Expect 4 Downstream Assets) ---")
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

    results_a = analyze_impact([entity_a], client=client)
    res_a = results_a[0]

    print(f"   --> Total Affected Downstream Assets ({len(res_a.total_affected_assets)}):")
    asset_types_a = set()
    for asset in res_a.total_affected_assets:
        owner_str = ", ".join(asset.owners) if asset.owners else "No owner"
        print(f"       - [{asset.entity_type.upper()}] {asset.name} (Hop Depth: {asset.depth}, Owners: {owner_str})")
        asset_types_a.add(asset.entity_type.lower())

    print(f"\n   --> Consolidated Affected Owners ({len(res_a.all_affected_owners)}): {res_a.all_affected_owners}")
    print(f"   --> Owner-to-Asset Mapping:")
    for owner, assets in res_a.owner_asset_map.items():
        print(f"       - {owner} owns: {assets}")

    # Verification assertions for Scenario A
    assert len(res_a.total_affected_assets) == 4, f"Expected 4 downstream assets for lifetime_value, found {len(res_a.total_affected_assets)}"
    assert "chart" in asset_types_a, "Chart missing from lifetime_value impact"
    assert "dashboard" in asset_types_a, "Dashboard missing from lifetime_value impact"
    assert "mlfeature" in asset_types_a, "ML Feature missing from lifetime_value impact"
    assert "mlmodel" in asset_types_a, "ML Model missing from lifetime_value impact"
    assert len(res_a.all_affected_owners) > 0, "Expected non-empty owner list for Scenario A"

    # SCENARIO B (THE PROOF): Drop first_order_at (Has NO downstream column dependents)
    logger.info("\n--- Scenario B (The Proof): Drop 'first_order_at' (Expect 0 Downstream Assets) ---")
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

    results_b = analyze_impact([entity_b], client=client)
    res_b = results_b[0]

    print(f"   --> Total Affected Downstream Assets ({len(res_b.total_affected_assets)}): {res_b.total_affected_assets}")
    print(f"   --> Consolidated Affected Owners ({len(res_b.all_affected_owners)}): {res_b.all_affected_owners}")

    # Verification assertions for Scenario B
    assert len(res_b.total_affected_assets) == 0, f"Expected 0 downstream assets for first_order_at, found {len(res_b.total_affected_assets)}"
    assert len(res_b.all_affected_owners) == 0, f"Expected 0 affected owners for first_order_at, found {len(res_b.all_affected_owners)}"

    print("\nSUCCESS: Phase 4 Column-Aware Analyzer verified! Scenario A returned 4 assets; Scenario B returned 0 assets, proving true column-level precision!")


if __name__ == "__main__":
    verify_analyzer()
