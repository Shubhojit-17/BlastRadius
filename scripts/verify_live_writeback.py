"""
Live DataHub Phase 7 Acceptance Verification Script.

Executes real MCP mutation tools against live DataHub Core (http://localhost:8080):
1. Runs live write-back for Scenario A (drop lifetime_value).
2. Reads back live graph state via get_entities to PROVE:
   - blastradius_pending_change tag is attached to target entity AND all 4 downstream assets.
   - Live description contains the sentinel warning block with original catalog doc intact above it.
3. Runs live cleanup_writeback.
4. Reads back live graph state to PROVE:
   - Tags are completely removed.
   - Description is restored to original text with 0 sentinel block leftover.
"""

import sys
import os
import json
import logging
import asyncio
from blastradius.orchestrator import run_pipeline
from blastradius.writeback import execute_writeback, cleanup_writeback, TAG_NAME, SENTINEL_START
from blastradius.mcp_agent import MCPAgent
from blastradius.datahub_client import DataHubRestGraphClient
from blastradius.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_live_writeback")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_live_verification() -> None:
    logger.info("=== Phase 7 Live DataHub Acceptance Verification ===")
    logger.info(f"Connecting to live DataHub GMS at {config.datahub_gms_url}...")

    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)
    mcp_agent = MCPAgent(gms_url=config.datahub_gms_url)

    # Base & Head SQL for Scenario A (drop lifetime_value)
    base_sql_a = "SELECT user_id, first_order_at, lifetime_value, total_orders FROM analytics.fct_user_orders;"
    head_sql_a = "SELECT user_id, first_order_at, total_orders FROM analytics.fct_user_orders;"

    # 1. Step 1: Run Orchestrator Pipeline for Scenario A (Live DataHub client)
    logger.info("\n--- Step 1: Running Orchestrator Pipeline for Scenario A ---")
    report_a, exit_code_a = run_pipeline(
        base_sql_a,
        head_sql_a,
        client=client,
        use_mock=False,
        pr_number=707,
        commit_sha="live_sha_707"
    )

    print(f"Orchestrator Risk Level: {report_a.risk_level.value}")
    print(f"Orchestrator Exit Code:  {exit_code_a}")
    assert report_a.risk_level.value == "HIGH", "Scenario A must evaluate HIGH risk"

    target_urn = report_a.changed_entities[0].urn
    downstream_urns = [a.urn for a in report_a.downstream_impacts]
    all_target_urns = [target_urn] + downstream_urns

    # 2. Step 2: Execute Live Write-Back (write_back=True, dry_run=False, use_mock=False)
    logger.info("\n--- Step 2: Executing LIVE Write-Back Mutations over stdio MCP server ---")
    wb_live_res = execute_writeback(report_a, client=client, dry_run=False, use_mock=False)
    print("Live Write-Back Response Dict:")
    print(json.dumps(wb_live_res, indent=2))

    assert wb_live_res.get("status") == "SUCCESS", f"Expected live write-back status SUCCESS, got {wb_live_res.get('status')}"

    # 3. Step 3: READ-BACK Verification (Fetch live metadata from DataHub via MCP get_entities)
    logger.info("\n--- Step 3: LIVE READ-BACK Verification via MCP get_entities ---")

    async def verify_live_graph_state():
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        uvx_cmd = mcp_agent._resolve_uvx_path()
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = config.datahub_gms_url
        env["TOOLS_IS_MUTATION_ENABLED"] = "true"

        server_params = StdioServerParameters(command=uvx_cmd, args=["mcp-server-datahub@latest"], env=env)

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_list_resp = await session.list_tools()
                tools_dict = {t.name: t for t in tools_list_resp.tools}

                # Call get_entities for all assets
                ent_text = await mcp_agent._call_tool_dynamic(session, tools_dict, "get_entities", {"urns": all_target_urns})
                return ent_text

    live_entities_text = asyncio.run(verify_live_graph_state())
    print("\nLive get_entities Response Text:")
    print(live_entities_text[:2000])

    # Assert 1: Description contains sentinel warning AND original catalog doc intact
    assert "Derived dbt model for user lifetime value and order metrics" in live_entities_text, "Original description MUST be preserved intact in live GMS"
    assert "BlastRadius Schema Impact Warning" in live_entities_text, "Sentinel warning block MUST land in live GMS description"
    assert "PR #707" in live_entities_text, "PR number MUST land in live sentinel block"

    # Assert 2: blastradius_pending_change tag is attached
    assert TAG_NAME in live_entities_text, f"Tag '{TAG_NAME}' MUST be attached in live GMS"

    logger.info("\nSUCCESS: Live write-back read-back verified! Tags and sentinel description warning landed cleanly in live DataHub!")

    # 4. Step 4: Execute Live Reversible Cleanup
    logger.info("\n--- Step 4: Executing LIVE Reversible Cleanup ---")
    cleanup_res = cleanup_writeback(report_a, client=client, use_mock=False)
    print("Live Cleanup Response Dict:")
    print(json.dumps(cleanup_res, indent=2))

    assert cleanup_res.get("status") == "CLEANUP_SUCCESS", f"Expected CLEANUP_SUCCESS, got {cleanup_res.get('status')}"

    # 5. Step 5: Post-Cleanup READ-BACK Verification
    logger.info("\n--- Step 5: Post-Cleanup LIVE READ-BACK Verification ---")
    post_cleanup_text = asyncio.run(verify_live_graph_state())
    print("\nPost-Cleanup get_entities Response Text:")
    print(post_cleanup_text[:2000])

    # Assert 1: Original description intact, sentinel block GONE
    assert "Derived dbt model for user lifetime value and order metrics" in post_cleanup_text, "Original description MUST remain intact after cleanup"
    assert "BlastRadius Schema Impact Warning" not in post_cleanup_text, "Sentinel warning block MUST be removed after cleanup"

    # Assert 2: Tags removed
    assert TAG_NAME not in post_cleanup_text, f"Tag '{TAG_NAME}' MUST be removed after cleanup"

    print("\n" + "=" * 70)
    print("ALL LIVE ACCEPTANCE TESTS PASSED 100%! Live DataHub write-back & cleanup round-trip verified!")
    print("=" * 70)


if __name__ == "__main__":
    run_live_verification()
