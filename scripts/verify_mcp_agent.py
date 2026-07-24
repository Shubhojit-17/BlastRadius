"""
Phase 6.5 Verification Script.

Executes deterministic Phase 4 Analyzer on dropping 'lifetime_value' from 'fct_user_orders',
then invokes MCPAgent to connect over stdio to mcp-server-datahub@latest, dynamically discover tool schemas,
enrich results using MCP read tools, verify visible dormant mutation tools, and print both
deterministic facts and the enriched risk narrative containing real MCP metadata.
"""

import asyncio
import logging
from blastradius.analyzer import analyze_impact
from blastradius.resolver import resolve_entities_to_urns
from blastradius.datahub_client import DataHubRestGraphClient
from blastradius.mcp_agent import MCPAgent
from blastradius.models import ChangedEntity, ColumnChange, ChangeType
from blastradius.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_mcp_agent")


async def run_verification() -> None:
    logger.info("=== Phase 6.5 DataHub MCP Agent Layer Verification ===")
    logger.info(f"Connecting DataHub SDK client to {config.datahub_gms_url}...")

    # Step 1: Run Phase 4 Deterministic Analyzer
    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)
    raw_entity = ChangedEntity(
        urn="",
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
    resolved_entity = resolve_entities_to_urns([raw_entity], env="PROD", client=client)[0]
    impact_results = analyze_impact([resolved_entity], client=client)
    impact_res = impact_results[0]

    # Step 2: Connect MCP Agent & Enrich Impact Analysis
    logger.info("\nLaunching MCP Agent over stdio to mcp-server-datahub@latest...")
    mcp_agent = MCPAgent(gms_url=config.datahub_gms_url)
    enriched_ctx, narrative = await mcp_agent.enrich_impact_analysis(impact_res)

    # Step 3: Print Verification Outputs
    print("\n" + "=" * 60)
    print("1. DISCOVERED MCP TOOL LIST:")
    print("=" * 60)
    print(f"Total Tools Discovered: {len(enriched_ctx.mcp_tools_discovered)}")
    print("Dormant Mutation Tools Visible:")
    for mut_tool in enriched_ctx.mcp_mutation_tools_visible:
        print(f"  [DORMANT MUTATION TOOL] - {mut_tool}")

    print("\n" + "=" * 60)
    print("2. READ TOOLS EXECUTED & DATA STATUS:")
    print("=" * 60)
    print(f"Read Tools Returning Data: {enriched_ctx.read_tools_with_data}")
    print("MCP Extracted Descriptions (from get_entities):")
    for name, desc in enriched_ctx.entity_descriptions.items():
        if not name.startswith("urn:li:"):
            print(f"  - {name}: \"{desc}\"")

    print("\nMCP Extracted Lineage Trace (from get_lineage_paths_between):")
    for trace in enriched_ctx.parsed_lineage_traces:
        print(f"  - {trace}")

    print("\n" + "=" * 60)
    print("3. DETERMINISTIC FACTS (FROM ANALYZER - GROUND TRUTH):")
    print("=" * 60)
    print(f"Target Entity: {impact_res.target_entity.dataset_name} ({impact_res.target_entity.urn})")
    print(f"Total Affected Downstream Assets: {len(impact_res.total_affected_assets)}")
    for asset in impact_res.total_affected_assets:
        owners = ", ".join(asset.owners) if asset.owners else "No owner"
        print(f"  - [{asset.entity_type.upper()}] {asset.name} (Hop Depth: {asset.depth}, Owners: {owners})")
    print(f"Consolidated Affected Owners: {impact_res.all_affected_owners}")

    print("\n" + "=" * 60)
    print("4. ENRICHED RISK NARRATIVE (FROM MCP AGENT):")
    print("=" * 60)
    print(narrative)
    print("=" * 60)

    # Step 4: Verification Assertions proving MCP content is in Narrative
    assert len(enriched_ctx.mcp_tools_discovered) >= 10, "Expected at least 10 MCP tools discovered"
    assert len(enriched_ctx.mcp_mutation_tools_visible) > 0, "Expected dormant mutation tools visible"
    assert len(enriched_ctx.read_tools_with_data) >= 2, f"Expected at least 2 read tools returning data, got {enriched_ctx.read_tools_with_data}"
    assert "get_entities" in enriched_ctx.read_tools_with_data, "get_entities should return data"
    assert "get_lineage_paths_between" in enriched_ctx.read_tools_with_data, "get_lineage_paths_between should return data"
    
    # Assert concrete MCP facts appear in the narrative text
    assert "Production XGBoost model" in narrative or "High level executive" in narrative, "Narrative must contain real entity description from MCP get_entities"
    assert "DATASET" in narrative or "MLFEATURE" in narrative or "user_ltv_feature" in narrative, "Narrative must contain real lineage trace from MCP get_lineage_paths_between"

    print("\nSUCCESS: Phase 6.5 verification passed 100%! Real MCP metadata (descriptions + lineage path trace) is actively embedded in the risk narrative!")


if __name__ == "__main__":
    asyncio.run(run_verification())
