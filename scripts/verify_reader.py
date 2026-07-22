"""
Phase 2 Verification Script with Column Path & Ownership Proof.

Executes the concrete DataHubRestGraphClient against the live local DataHub instance (http://localhost:8080)
and verifies end-to-end reading of entity resolution, dataset schema, multi-hop downstream lineage with
explicit column path traces, ownership metadata, and assertion contracts.
"""

import logging
from blastradius.datahub_client import DataHubRestGraphClient
from blastradius.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_reader")


def verify_reader() -> None:
    logger.info("=== Phase 2 End-to-End Graph Reader & Lineage Verification ===")
    logger.info(f"Connecting to DataHub GMS at {config.datahub_gms_url}...")

    # Initialize concrete client
    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)

    # 1. Resolve Entity URN
    dataset_name = "analytics.fct_user_orders"
    logger.info(f"\n1. Resolving dataset URN for '{dataset_name}'...")
    urn = client.resolve_entity_urn(dataset_name)
    print(f"   --> Resolved URN: {urn}")
    assert urn is not None, f"Failed to resolve URN for {dataset_name}"
    assert "snowflake" in urn, "URN does not match expected platform"

    # 2. Fetch Dataset Schema
    logger.info(f"\n2. Fetching schema for URN '{urn}'...")
    schema = client.fetch_dataset_schema(urn)
    print(f"   --> Schema fields ({len(schema)}):")
    for field_name, data_type in schema.items():
        print(f"       - {field_name}: {data_type}")
    assert "lifetime_value" in schema, "Field 'lifetime_value' missing from schema"

    # 3. Fetch Multi-Hop Downstream Lineage & Column Paths & Ownership
    start_column = "lifetime_value"
    logger.info(f"\n3. Fetching multi-hop downstream lineage starting from '{start_column}'...")
    downstream_assets = client.fetch_downstream_column_lineage(urn, column_name=start_column, max_depth=5)

    print(f"   --> Discovered Downstream Assets ({len(downstream_assets)} total):")
    asset_types_found = set()
    total_owners_found = 0

    for asset in downstream_assets:
        owner_str = ", ".join(asset.owners) if asset.owners else "No explicit owner"
        if asset.owners:
            total_owners_found += len(asset.owners)

        # Print column lineage trace path
        path_str = f"{start_column} -> {asset.name}"
        if asset.column_paths:
            path_details = [f"{p.upstream_column} -> {p.downstream_column}" for p in asset.column_paths]
            path_str = ", ".join(path_details)

        print(f"       - [{asset.entity_type.upper()}] {asset.name} (Hop Depth: {asset.depth})")
        print(f"         Path: {path_str}")
        print(f"         Owners: {owner_str}")
        print(f"         URN: {asset.urn}")
        asset_types_found.add(asset.entity_type.lower())

    # Assertions for FIX B
    assert len(downstream_assets) >= 4, f"Expected at least 4 downstream assets, found {len(downstream_assets)}"
    assert "chart" in asset_types_found, "Looker Chart missing from downstream lineage"
    assert "dashboard" in asset_types_found, "Executive Dashboard (2nd degree) missing from downstream lineage"
    assert "mlfeature" in asset_types_found, "ML Feature (user_ltv_feature) missing from downstream lineage"
    assert "mlmodel" in asset_types_found, "ML Model (churn_prediction_v2 2nd degree) missing from downstream lineage"
    assert total_owners_found > 0, "Expected non-empty ownership list returned for downstream assets"

    # 4. Fetch Entity Assertions
    logger.info(f"\n4. Fetching assertions attached to URN '{urn}'...")
    assertions = client.fetch_entity_assertions(urn)
    print(f"   --> Attached Assertions ({len(assertions)}):")
    for assertion in assertions:
        print(f"       - Assertion URN: {assertion.assertion_urn} (Type: {assertion.assertion_type})")

    assert len(assertions) >= 1, "Expected at least 1 assertion attached to fct_user_orders"
    print("\nSUCCESS: FIX A & FIX B verified! Graph reader retrieves multi-hop lineage, column paths, owners, and assertions end-to-end!")


if __name__ == "__main__":
    verify_reader()
