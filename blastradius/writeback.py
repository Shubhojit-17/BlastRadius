"""
DataHub Metadata Write-Back Module.

Writes BlastRadius assessment findings back into DataHub metadata graph via DataHub MCP mutation tools
(add_tags, update_description, add_structured_properties).

Includes strict guardrails:
- Default OFF (write_back flag required)
- Dry-run mode (logs planned mutations without executing)
- Sentinel Read-Modify-Write description preservation (never clobbers catalog docs)
- Idempotent and reversible cleanup (cleanup_writeback resets graph to original state)
"""

import sys
import os
import re
import json
import logging
import asyncio
from typing import List, Dict, Tuple, Optional, Any

from blastradius.models import AssessmentReport, RiskLevel
from blastradius.datahub_client import DataHubClient, DataHubRestGraphClient, MockDataHubClient
from blastradius.mcp_agent import MCPAgent
from blastradius.config import config

logger = logging.getLogger("writeback")

SENTINEL_START = "[BLASTRADIUS:START]"
SENTINEL_END = "[BLASTRADIUS:END]"
TAG_NAME = "blastradius_pending_change"


def format_sentinel_warning(report: AssessmentReport) -> str:
    """Formats the warning markdown block wrapped in visible sentinel markers."""
    target_entity = report.changed_entities[0] if report.changed_entities else None
    dataset_name = target_entity.dataset_name if target_entity else "dataset"
    cols = ", ".join([c.column_name for c in target_entity.column_changes]) if target_entity else "column"
    change_type = target_entity.change_type.value if target_entity else "MODIFIED"

    violated_str = ", ".join([vc.assertion_urn.split(":")[-1] for vc in report.contract_violations]) if report.contract_violations else "None"

    warning = (
        f"{SENTINEL_START}\n"
        f"### ⚠️ BlastRadius Schema Impact Warning (PR #{report.pr_number})\n"
        f"- **Risk Verdict:** `{report.risk_level.value} RISK` (Score: `{report.risk_score:.1f}/100.0`)\n"
        f"- **Column Modification:** `{change_type}` on `{cols}`\n"
        f"- **Downstream Assets Affected:** `{len(report.downstream_impacts)}` (Max Depth: `{max([a.depth for a in report.downstream_impacts]) if report.downstream_impacts else 1}`)\n"
        f"- **Data Contract Violated:** `{violated_str}`\n"
        f"- **Commit SHA:** `{report.commit_sha}`\n"
        f"{SENTINEL_END}"
    )
    return warning


def apply_read_modify_write_description(original_desc: str, warning_block: str) -> str:
    """
    Appends or updates sentinel warning block using re.DOTALL, preserving original description.
    """
    clean_original = original_desc.strip()
    pattern = rf"\n\n{re.escape(SENTINEL_START)}.*?{re.escape(SENTINEL_END)}"

    if re.search(pattern, clean_original, flags=re.DOTALL):
        return re.sub(pattern, f"\n\n{warning_block}", clean_original, flags=re.DOTALL)
    elif SENTINEL_START in clean_original:
        pattern_alt = rf"{re.escape(SENTINEL_START)}.*?{re.escape(SENTINEL_END)}"
        return re.sub(pattern_alt, warning_block, clean_original, flags=re.DOTALL)
    else:
        if clean_original:
            return f"{clean_original}\n\n{warning_block}"
        return warning_block


def strip_sentinel_warning(desc_with_warning: str) -> str:
    """
    Strips sentinel warning block and trailing whitespace, restoring exact original description.
    """
    pattern = rf"\n\n{re.escape(SENTINEL_START)}.*?{re.escape(SENTINEL_END)}"
    stripped = re.sub(pattern, "", desc_with_warning, flags=re.DOTALL)

    if SENTINEL_START in stripped:
        pattern_alt = rf"{re.escape(SENTINEL_START)}.*?{re.escape(SENTINEL_END)}"
        stripped = re.sub(pattern_alt, "", stripped, flags=re.DOTALL)

    return stripped.strip()


def ensure_tag_exists(client: Optional[DataHubClient], tag_name: str = TAG_NAME) -> None:
    """Ensures the tag entity exists in DataHub GMS before calling add_tags."""
    if client and hasattr(client, "graph"):
        try:
            from datahub.emitter.mcp import MetadataChangeProposalWrapper
            from datahub.metadata.schema_classes import TagPropertiesClass, ChangeTypeClass
            tag_urn = f"urn:li:tag:{tag_name}"
            tag_mcp = MetadataChangeProposalWrapper(
                entityType="tag",
                entityUrn=tag_urn,
                changeType=ChangeTypeClass.UPSERT,
                aspectName="tagProperties",
                aspect=TagPropertiesClass(name=tag_name, description="Pending schema change warning added by BlastRadius")
            )
            client.graph.emit(tag_mcp)
        except Exception as e:
            logger.warning(f"Could not auto-create tag entity in GMS: {e}")


def execute_writeback(
    report: AssessmentReport,
    client: Optional[DataHubClient] = None,
    dry_run: bool = False,
    use_mock: bool = False
) -> Dict[str, Any]:
    """
    Executes DataHub metadata write-back via DataHub MCP mutation tools or mock fallback.

    Args:
        report: AssessmentReport from orchestrator.
        client: DataHubClient instance.
        dry_run: If True, logs planned mutations without executing.
        use_mock: If True, operates in zero-setup offline mock mode.

    Returns:
        Dict summarizing executed mutation actions and target URNs.
    """
    if not report.changed_entities:
        logger.info("[WRITEBACK] No changed entities to write back.")
        return {"status": "SKIPPED", "mutations": []}

    ensure_tag_exists(client, TAG_NAME)

    target_entity = report.changed_entities[0]
    target_urn = target_entity.urn
    affected_urns = [target_urn] + [a.urn for a in report.downstream_impacts]

    planned_mutations: List[Dict[str, Any]] = []

    # 1. Plan Tagging Mutations (add_tags)
    for urn in affected_urns:
        planned_mutations.append({
            "tool": "add_tags",
            "target_urn": urn,
            "args": {"entity_urn": urn, "tag_name": TAG_NAME}
        })

    # 2. Plan Description Mutation (update_description)
    warning_block = format_sentinel_warning(report)
    planned_mutations.append({
        "tool": "update_description",
        "target_urn": target_urn,
        "args": {"entity_urn": target_urn, "description": warning_block}
    })

    # 3. Plan Structured Property Mutation (add_structured_properties best-effort)
    planned_mutations.append({
        "tool": "add_structured_properties",
        "target_urn": target_urn,
        "args": {
            "entity_urns": [target_urn],
            "property_values": [
                {"property_urn": "urn:li:structuredProperty:blastradius_risk_level", "values": [report.risk_level.value]},
                {"property_urn": "urn:li:structuredProperty:blastradius_pr", "values": [f"#{report.pr_number}"]}
            ]
        }
    })

    # Check Dry-Run or Offline Fallback Conditions
    if dry_run or use_mock:
        logger.info(f"[WRITEBACK] Operating in {'DRY-RUN' if dry_run else 'OFFLINE MOCK'} mode. Logging {len(planned_mutations)} planned mutations:")
        for mut in planned_mutations:
            logger.info(f"  [DRY-RUN MUTATION] Tool: '{mut['tool']}' | Target URN: '{mut['target_urn']}' | Args: {mut['args']}")
        return {
            "status": "DRY_RUN",
            "dry_run": True,
            "planned_mutations": planned_mutations,
            "executed_count": 0
        }

    # Live Stdio Execution via MCPAgent
    logger.info(f"[WRITEBACK] Executing live write-back mutations on DataHub Core ({config.datahub_gms_url})...")
    mcp_agent = MCPAgent(gms_url=config.datahub_gms_url)

    async def run_live_mutations():
        # Spawn stdio server and execute mutation tools
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        uvx_cmd = mcp_agent._resolve_uvx_path()
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = config.datahub_gms_url
        env["TOOLS_IS_MUTATION_ENABLED"] = "true"
        env.pop("DATAHUB_GMS_TOKEN", None)

        server_params = StdioServerParameters(command=uvx_cmd, args=["mcp-server-datahub@latest"], env=env)

        results = []
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_list_resp = await session.list_tools()
                tools_dict = {t.name: t for t in tools_list_resp.tools}

                # a. Fetch current description for read-modify-write
                ent_text = await mcp_agent._call_tool_dynamic(session, tools_dict, "get_entities", {"urns": [target_urn]})
                orig_desc = ""
                if ent_text:
                    descs, _ = mcp_agent._parse_entities_response(ent_text)
                    orig_desc = descs.get(target_urn) or descs.get(target_entity.dataset_name) or ""

                new_desc = apply_read_modify_write_description(orig_desc, warning_block)

                # b. Execute add_tags for target and affected assets
                for urn in affected_urns:
                    tag_res = await mcp_agent._call_tool_dynamic(session, tools_dict, "add_tags", {"entity_urn": urn, "tag_name": TAG_NAME})
                    results.append({"tool": "add_tags", "target_urn": urn, "result": str(tag_res)})

                # c. Execute update_description
                desc_res = await mcp_agent._call_tool_dynamic(session, tools_dict, "update_description", {"entity_urn": target_urn, "description": new_desc})
                results.append({"tool": "update_description", "target_urn": target_urn, "result": str(desc_res), "updated_description": new_desc})

                # d. Best-effort add_structured_properties
                try:
                    sp_res = await mcp_agent._call_tool_dynamic(session, tools_dict, "add_structured_properties", {
                        "entity_urn": target_urn,
                        "properties": {"blastradius_risk_level": report.risk_level.value}
                    })
                    results.append({"tool": "add_structured_properties", "target_urn": target_urn, "result": str(sp_res)})
                except Exception as ex:
                    logger.warning(f"Structured properties fail-soft warning: {ex}")

        return results

    try:
        live_results = asyncio.run(run_live_mutations())
        logger.info(f"Live write-back complete ({len(live_results)} mutations executed).")
        return {"status": "SUCCESS", "dry_run": False, "results": live_results}
    except Exception as e:
        logger.warning(f"Live write-back encountered connection error, falling back to dry-run mode: {e}")
        return {"status": "FALLBACK_DRY_RUN", "dry_run": True, "planned_mutations": planned_mutations}


def cleanup_writeback(
    report: AssessmentReport,
    client: Optional[DataHubClient] = None,
    use_mock: bool = False
) -> Dict[str, Any]:
    """
    Reversible cleanup: removes blastradius tags and strips sentinel description block from DataHub GMS.
    """
    if not report.changed_entities:
        return {"status": "SKIPPED"}

    target_entity = report.changed_entities[0]
    target_urn = target_entity.urn
    affected_urns = [target_urn] + [a.urn for a in report.downstream_impacts]

    if use_mock:
        logger.info("[CLEANUP] Offline Mock Mode -- Simulating tag removal & description cleanup.")
        return {"status": "MOCK_CLEANUP_SUCCESS", "cleaned_urns": affected_urns}

    logger.info(f"[CLEANUP] Executing reversible cleanup on DataHub Core ({config.datahub_gms_url})...")
    mcp_agent = MCPAgent(gms_url=config.datahub_gms_url)

    async def run_cleanup():
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        uvx_cmd = mcp_agent._resolve_uvx_path()
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = config.datahub_gms_url
        env["TOOLS_IS_MUTATION_ENABLED"] = "true"

        server_params = StdioServerParameters(command=uvx_cmd, args=["mcp-server-datahub@latest"], env=env)

        cleanup_results = []
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_list_resp = await session.list_tools()
                tools_dict = {t.name: t for t in tools_list_resp.tools}

                # a. Remove tags from target and affected assets
                for urn in affected_urns:
                    rem_res = await mcp_agent._call_tool_dynamic(session, tools_dict, "remove_tags", {"entity_urn": urn, "tag_name": TAG_NAME})
                    cleanup_results.append({"tool": "remove_tags", "target_urn": urn, "result": str(rem_res)})

                # b. Read description and strip sentinel warning block
                ent_text = await mcp_agent._call_tool_dynamic(session, tools_dict, "get_entities", {"urns": [target_urn]})
                if ent_text:
                    descs, _ = mcp_agent._parse_entities_response(ent_text)
                    curr_desc = descs.get(target_urn) or descs.get(target_entity.dataset_name) or ""
                    cleaned_desc = strip_sentinel_warning(curr_desc)

                    clean_res = await mcp_agent._call_tool_dynamic(session, tools_dict, "update_description", {"entity_urn": target_urn, "description": cleaned_desc})
                    cleanup_results.append({"tool": "update_description", "target_urn": target_urn, "restored_description": cleaned_desc})

        return cleanup_results

    try:
        res = asyncio.run(run_cleanup())
        logger.info("[CLEANUP] Reversible cleanup execution complete!")
        return {"status": "CLEANUP_SUCCESS", "results": res}
    except Exception as e:
        logger.warning(f"[CLEANUP] Connection error during cleanup: {e}")
        return {"status": "CLEANUP_FAILED", "error": str(e)}
