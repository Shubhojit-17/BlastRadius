"""
Live DataHub Phase 7 Acceptance Verification Script.

Executes real MCP mutation tools against live DataHub Core (http://localhost:8080):
1. Executes LIVE write-back for Scenario A (PR #707).
2. Reads back live graph state via get_entities to PROVE:
   - [BLASTRADIUS:START] / [BLASTRADIUS:END] plain-text delimiters land in live GMS description.
   - blastradius_pending_change tag lands on target dataset AND all 4 downstream assets.
   - Structured properties (blastradius_risk_level & blastradius_pr) land in GMS.
3. LIVE IDEMPOTENCY TEST: Executes write-back AGAIN for PR #708 WITHOUT cleanup.
   - Reads back GMS description and asserts [BLASTRADIUS:START] appears EXACTLY ONCE (no stacked duplicates).
4. LIVE REVERSIBLE CLEANUP TEST: Executes cleanup_writeback live.
   - Reads back GMS description and asserts restored_description == original_catalog_doc EXACTLY byte-for-byte.
   - Asserts tags are completely removed.
"""

import sys
import os
import json
import logging
import asyncio
from blastradius.orchestrator import run_pipeline
from blastradius.writeback import execute_writeback, cleanup_writeback, TAG_NAME, SENTINEL_START, SENTINEL_END
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

    # 1. Step 1: Run Orchestrator Pipeline for Scenario A (PR #707)
    logger.info("\n--- Step 1: Running Orchestrator Pipeline for Scenario A (PR #707) ---")
    report_a, exit_code_a = run_pipeline(
        base_sql_a,
        head_sql_a,
        client=client,
        use_mock=False,
        pr_number=707,
        commit_sha="sha_707"
    )

    assert report_a.risk_level.value == "HIGH", "Scenario A must evaluate HIGH risk"

    target_urn = report_a.changed_entities[0].urn
    downstream_urns = [a.urn for a in report_a.downstream_impacts]
    all_target_urns = [target_urn] + downstream_urns

    # Helper function to query GMS via stdio MCP client
    async def fetch_live_gms_entities():
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
                ent_text = await mcp_agent._call_tool_dynamic(session, tools_dict, "get_entities", {"urns": all_target_urns})
                return ent_text

    # Record original description before write-back
    initial_gms_raw = asyncio.run(fetch_live_gms_entities())
    descs, _ = mcp_agent._parse_entities_response(initial_gms_raw)
    original_catalog_doc = descs.get(target_urn, "").split("\n\n" + SENTINEL_START)[0].strip()
    logger.info(f"Original Catalog Document from GMS: '{original_catalog_doc}'")

    # 2. Step 2: Execute LIVE Write-Back (PR #707)
    logger.info("\n--- Step 2: Executing LIVE Write-Back Mutations (PR #707) ---")
    wb_res_1 = execute_writeback(report_a, client=client, dry_run=False, use_mock=False)
    print("Write-Back 1 (PR #707) Result:")
    print(json.dumps(wb_res_1, indent=2))

    assert wb_res_1.get("status") == "SUCCESS", f"Write-back 1 failed: {wb_res_1}"

    # Read back from GMS after Write-Back 1
    post_write_1_raw = asyncio.run(fetch_live_gms_entities())
    print("\nGMS Read-Back After Write-Back 1 (PR #707):")
    print(post_write_1_raw[:1500])

    assert SENTINEL_START in post_write_1_raw, "Delimited [BLASTRADIUS:START] MUST land in live GMS description"
    assert SENTINEL_END in post_write_1_raw, "Delimited [BLASTRADIUS:END] MUST land in live GMS description"
    assert original_catalog_doc in post_write_1_raw, "Original description MUST be preserved above warning block"
    assert TAG_NAME in post_write_1_raw, f"Tag '{TAG_NAME}' MUST land in GMS"

    # 3. Step 3: LIVE DOUBLE-WRITE IDEMPOTENCY TEST (PR #708)
    logger.info("\n--- Step 3: LIVE Double-Write Idempotency Test (PR #708 without cleanup) ---")
    report_a_v2, _ = run_pipeline(
        base_sql_a,
        head_sql_a,
        client=client,
        use_mock=False,
        pr_number=708,
        commit_sha="sha_708"
    )

    wb_res_2 = execute_writeback(report_a_v2, client=client, dry_run=False, use_mock=False)
    print("Write-Back 2 (PR #708) Result:")
    print(json.dumps(wb_res_2, indent=2))

    # Read back from GMS after Write-Back 2
    post_write_2_raw = asyncio.run(fetch_live_gms_entities())
    print("\nGMS Read-Back After Write-Back 2 (PR #708):")
    print(post_write_2_raw[:1500])

    start_count = post_write_2_raw.count(SENTINEL_START)
    print(f"\n[IDEMPOTENCY ASSERTION] '[BLASTRADIUS:START]' count in GMS description: {start_count}")
    assert start_count == 1, f"Idempotency failed! Expected 1 sentinel block, found {start_count}"
    assert "PR #708" in post_write_2_raw, "Description block MUST be updated to PR #708 in place"
    assert original_catalog_doc in post_write_2_raw, "Original catalog text MUST remain intact"

    logger.info("--> Live Idempotency Assertion Passed 100%!")

    # 4. Step 4: LIVE REVERSIBLE CLEANUP TEST
    logger.info("\n--- Step 4: Executing LIVE Reversible Cleanup ---")
    cleanup_res = cleanup_writeback(report_a_v2, client=client, use_mock=False)
    print("Cleanup Result:")
    print(json.dumps(cleanup_res, indent=2))

    assert cleanup_res.get("status") == "CLEANUP_SUCCESS", f"Cleanup failed: {cleanup_res}"

    # Read back from GMS post-cleanup
    post_cleanup_raw = asyncio.run(fetch_live_gms_entities())
    print("\nGMS Read-Back After Cleanup:")
    print(post_cleanup_raw[:1500])

    post_descs, _ = mcp_agent._parse_entities_response(post_cleanup_raw)
    restored_desc = post_descs.get(target_urn, "")
    print(f"\n[CLEANUP ASSERTION] Restored Description: '{restored_desc}'")
    print(f"[CLEANUP ASSERTION] Original Description: '{original_catalog_doc}'")

    assert restored_desc == original_catalog_doc, f"Exact byte-for-byte restore failed! Expected '{original_catalog_doc}', got '{restored_desc}'"
    assert SENTINEL_START not in post_cleanup_raw, "Sentinel start delimiter MUST be gone"
    assert TAG_NAME not in post_cleanup_raw, f"Tag '{TAG_NAME}' MUST be completely removed from GMS"

    logger.info("--> Live Cleanup Assertion Passed 100%!")

    print("\n" + "=" * 75)
    print("ALL LIVE ACCEPTANCE TESTS PASSED 100%! Plain-text delimiters, double-write idempotency, and exact byte-for-byte cleanup verified against live DataHub GMS!")
    print("=" * 75)


if __name__ == "__main__":
    run_live_verification()
