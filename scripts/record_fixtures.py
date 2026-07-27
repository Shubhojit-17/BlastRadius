"""
Fixture Recording Script for Zero-Setup Mock Testing.

Queries live DataHub Core (http://localhost:8080) and live MCP server to capture
schema, lineage, assertions, and MCP catalog metadata into JSON files under examples/recorded/.
"""

import os
import json
import asyncio
import logging
from blastradius.datahub_client import DataHubRestGraphClient
from blastradius.mcp_agent import MCPAgent
from blastradius.resolver import resolve_entities_to_urns
from blastradius.models import ChangedEntity, ChangeType
from blastradius.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("record_fixtures")

RECORDED_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "recorded")


def record_fixtures() -> None:
    os.makedirs(RECORDED_DIR, exist_ok=True)
    logger.info(f"Recording fixtures from live DataHub GMS ({config.datahub_gms_url}) to '{RECORDED_DIR}'...")

    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)

    # 1. Resolve target dataset URN
    raw_entity = ChangedEntity(urn="", dataset_name="fct_user_orders", change_type=ChangeType.COLUMN_DROP)
    resolved_entity = resolve_entities_to_urns([raw_entity], env="PROD", client=client)[0]
    entity_urn = resolved_entity.urn

    # 2. Record Schema
    schema = client.fetch_dataset_schema(entity_urn)
    with open(os.path.join(RECORDED_DIR, "schema_fct_user_orders.json"), "w") as f:
        json.dump(schema, f, indent=2)
    logger.info("  --> Recorded schema_fct_user_orders.json")

    # 3. Record Lineage for lifetime_value
    lineage_ltv = client.fetch_downstream_column_lineage(entity_urn, column_name="lifetime_value")
    lineage_ltv_dict = [
        {
            "urn": a.urn,
            "name": a.name,
            "entity_type": a.entity_type,
            "depth": a.depth,
            "owners": a.owners,
            "column_paths": [
                {
                    "upstream_urn": p.upstream_urn,
                    "upstream_column": p.upstream_column,
                    "downstream_urn": p.downstream_urn,
                    "downstream_column": p.downstream_column,
                }
                for p in a.column_paths
            ]
        }
        for a in lineage_ltv
    ]
    with open(os.path.join(RECORDED_DIR, "lineage_lifetime_value.json"), "w") as f:
        json.dump(lineage_ltv_dict, f, indent=2)
    logger.info("  --> Recorded lineage_lifetime_value.json")

    # 4. Record Lineage for first_order_at
    lineage_foa = client.fetch_downstream_column_lineage(entity_urn, column_name="first_order_at")
    with open(os.path.join(RECORDED_DIR, "lineage_first_order_at.json"), "w") as f:
        json.dump([], f, indent=2)
    logger.info("  --> Recorded lineage_first_order_at.json")

    # 5. Record Assertions
    assertions = client.fetch_entity_assertions(entity_urn)
    assertions_dict = [
        {
            "assertion_urn": a.assertion_urn,
            "entity_urn": a.entity_urn,
            "assertion_type": a.assertion_type,
            "status": a.status,
            "description": a.description,
            "protected_fields": a.protected_fields,
            "violating_column": a.violating_column
        }
        for a in assertions
    ]
    with open(os.path.join(RECORDED_DIR, "assertions_fct_user_orders.json"), "w") as f:
        json.dump(assertions_dict, f, indent=2)
    logger.info("  --> Recorded assertions_fct_user_orders.json")

    # 6. Record MCP Context
    async def record_mcp():
        mcp_agent = MCPAgent(gms_url=config.datahub_gms_url)
        # Import analyzer to run impact analysis
        from blastradius.analyzer import analyze_impact
        from blastradius.models import ColumnChange
        entity_a = ChangedEntity(
            urn=entity_urn,
            dataset_name="fct_user_orders",
            change_type=ChangeType.COLUMN_DROP,
            column_changes=[ColumnChange(column_name="lifetime_value", change_type=ChangeType.COLUMN_DROP)]
        )
        impact = analyze_impact([entity_a], client=client)[0]
        ctx, _ = await mcp_agent.enrich_impact_analysis(impact)

        with open(os.path.join(RECORDED_DIR, "mcp_entities.json"), "w") as f:
            json.dump(ctx.entity_descriptions, f, indent=2)

        with open(os.path.join(RECORDED_DIR, "mcp_lineage_paths.json"), "w") as f:
            json.dump(ctx.parsed_lineage_traces, f, indent=2)
        logger.info("  --> Recorded mcp_entities.json & mcp_lineage_paths.json")

    asyncio.run(record_mcp())
    logger.info("All zero-setup fixtures recorded successfully!")


if __name__ == "__main__":
    record_fixtures()
