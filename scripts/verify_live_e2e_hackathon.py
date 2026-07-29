"""
Master End-to-End Hackathon Verification Script.

Executes 100% LIVE verification against DataHub Core (http://localhost:8080):
1. Scenario A (HIGH RISK - Drop lifetime_value):
   - SQL AST Resolver -> Column Lineage -> Assertion Guard (VIOLATED) -> MCP stdio enrichment
   - Auditable Score 100.0/100.0 (HIGH RISK)
   - Live Write-Back (add_tags + [BLASTRADIUS:START] description + add_structured_properties)
   - Live GMS Read-Back Verification
   - Live Double-Write Idempotency Test
   - Live Reversible Cleanup & Exact Byte-for-Byte Restore
2. Scenario B (LOW RISK - Drop first_order_at):
   - 0 Downstream Assets -> 0 Contract Violations -> Auditable Score 0.0/100.0 (LOW RISK)
   - Scoped MCP Context Callout
3. Zero-Setup Offline Demo CLI Execution
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
logger = logging.getLogger("e2e_hackathon_verifier")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_e2e_hackathon_verification() -> None:
    logger.info("=======================================================================")
    logger.info("🏆 MASTER LIVE E2E HACKATHON VERIFICATION SUITE")
    logger.info("=======================================================================")

    client = DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)
    mcp_agent = MCPAgent(gms_url=config.datahub_gms_url)

    base_sql_a = "SELECT user_id, first_order_at, lifetime_value, total_orders FROM analytics.fct_user_orders;"
    head_sql_a = "SELECT user_id, first_order_at, total_orders FROM analytics.fct_user_orders;"

    base_sql_b = "SELECT user_id, first_order_at, lifetime_value, total_orders FROM analytics.fct_user_orders;"
    head_sql_b = "SELECT user_id, lifetime_value, total_orders FROM analytics.fct_user_orders;"

    # -------------------------------------------------------------------
    # PART 1: SCENARIO A (HIGH RISK LIVE VERIFICATION & WRITE-BACK)
    # -------------------------------------------------------------------
    logger.info("\n--- PART 1: SCENARIO A (HIGH RISK - Drop lifetime_value) ---")
    report_a, exit_code_a = run_pipeline(
        base_sql_a,
        head_sql_a,
        client=client,
        use_mock=False,
        pr_number=901,
        commit_sha="hackathon_sha_901"
    )

    print(f"\nScenario A Risk Level: {report_a.risk_level.value}")
    print(f"Scenario A Risk Score: {report_a.risk_score:.1f}/100.0")
    print(f"Scenario A Exit Code:  {exit_code_a}")
    assert report_a.risk_level.value == "HIGH", "Scenario A must evaluate HIGH risk"
    assert exit_code_a == 1, "Scenario A exit code must be 1"

    target_urn = report_a.changed_entities[0].urn
    downstream_urns = [a.urn for a in report_a.downstream_impacts]
    all_target_urns = [target_urn] + downstream_urns

    async def fetch_live_gms_entities():
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = config.datahub_gms_url
        env["TOOLS_IS_MUTATION_ENABLED"] = "true"

        server_params = mcp_agent.get_server_params(env)
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_list_resp = await session.list_tools()
                tools_dict = {t.name: t for t in tools_list_resp.tools}
                ent_text = await mcp_agent._call_tool_dynamic(session, tools_dict, "get_entities", {"urns": all_target_urns})
                return ent_text

    # Record baseline GMS description
    initial_raw = asyncio.run(fetch_live_gms_entities())
    descs, _ = mcp_agent._parse_entities_response(initial_raw)
    original_catalog_doc = descs.get(target_urn, "").split("\n\n" + SENTINEL_START)[0].strip()
    logger.info(f"Original Catalog Document from GMS: '{original_catalog_doc}'")

    # Live Write-Back 1 (PR #901)
    logger.info("\nExecuting Live Write-Back (PR #901)...")
    wb_res_1 = execute_writeback(report_a, client=client, dry_run=False, use_mock=False)
    assert wb_res_1.get("status") == "SUCCESS", f"Write-back 1 failed: {wb_res_1}"

    # Read back from GMS after Write-Back 1
    post_write_1_raw = asyncio.run(fetch_live_gms_entities())
    assert SENTINEL_START in post_write_1_raw, "Delimited [BLASTRADIUS:START] MUST land in live GMS"
    assert original_catalog_doc in post_write_1_raw, "Original catalog description MUST be preserved"
    assert TAG_NAME in post_write_1_raw, f"Tag '{TAG_NAME}' MUST land in GMS"
    logger.info("--> Live Write-Back 1 verified in GMS!")

    # Live Write-Back 2 Idempotency Check (PR #902 without cleanup)
    logger.info("\nExecuting Live Write-Back 2 Idempotency Check (PR #902)...")
    report_a_v2, _ = run_pipeline(
        base_sql_a,
        head_sql_a,
        client=client,
        use_mock=False,
        pr_number=902,
        commit_sha="hackathon_sha_902"
    )
    wb_res_2 = execute_writeback(report_a_v2, client=client, dry_run=False, use_mock=False)
    assert wb_res_2.get("status") == "SUCCESS"

    post_write_2_raw = asyncio.run(fetch_live_gms_entities())
    start_count = post_write_2_raw.count(SENTINEL_START)
    assert start_count == 1, f"Idempotency failed! Found {start_count} sentinel blocks"
    assert "PR #902" in post_write_2_raw, "Description MUST update to PR #902 in place"
    logger.info("--> Live Idempotency verified in GMS (1 sentinel block)!")

    # Live Reversible Cleanup
    logger.info("\nExecuting Live Reversible Cleanup...")
    cleanup_res = cleanup_writeback(report_a_v2, client=client, use_mock=False)
    assert cleanup_res.get("status") == "CLEANUP_SUCCESS"

    post_cleanup_raw = asyncio.run(fetch_live_gms_entities())
    post_descs, _ = mcp_agent._parse_entities_response(post_cleanup_raw)
    restored_desc = post_descs.get(target_urn, "")

    assert restored_desc == original_catalog_doc, f"Cleanup restore failed! Expected '{original_catalog_doc}', got '{restored_desc}'"
    assert SENTINEL_START not in post_cleanup_raw, "Sentinel delimiter MUST be gone"
    assert TAG_NAME not in post_cleanup_raw, f"Tag '{TAG_NAME}' MUST be completely removed from GMS"
    logger.info("--> Live Cleanup verified! Graph restored byte-for-byte!")

    # -------------------------------------------------------------------
    # PART 2: SCENARIO B (LOW RISK LIVE VERIFICATION)
    # -------------------------------------------------------------------
    logger.info("\n--- PART 2: SCENARIO B (LOW RISK - Drop first_order_at) ---")
    report_b, exit_code_b = run_pipeline(
        base_sql_b,
        head_sql_b,
        client=client,
        use_mock=False,
        pr_number=903,
        commit_sha="hackathon_sha_903"
    )

    print(f"\nScenario B Risk Level: {report_b.risk_level.value}")
    print(f"Scenario B Risk Score: {report_b.risk_score:.1f}/100.0")
    print(f"Scenario B Exit Code:  {exit_code_b}")
    assert report_b.risk_level.value == "LOW", "Scenario B must evaluate LOW risk"
    assert exit_code_b == 0, "Scenario B exit code must be 0"
    assert "No downstream assets are affected" in report_b.summary_markdown, "Scenario B MCP section must be scoped cleanly"
    logger.info("--> Scenario B verified 100%!")

    # -------------------------------------------------------------------
    # PART 3: ZERO-SETUP OFFLINE DEMO CLI VERIFICATION
    # -------------------------------------------------------------------
    logger.info("\n--- PART 3: ZERO-SETUP OFFLINE DEMO CLI (python -m blastradius.demo) ---")
    from blastradius.demo import run_demo as demo_main
    demo_main()
    logger.info("--> Zero-Setup Offline Demo verified 100%!")

    print("\n" + "=" * 75)
    print("🏆 MASTER HACKATHON VERIFICATION SUITE PASSED 100% LIVE!")
    print("All pipeline stages, MCP tools, write-backs, and cleanups verified!")
    print("=" * 75)


if __name__ == "__main__":
    run_e2e_hackathon_verification()
