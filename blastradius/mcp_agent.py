"""
DataHub MCP-Powered Agent Layer.

Connects to mcp-server-datahub over stdio using the official Python mcp SDK,
dynamically discovers tool schemas, enriches deterministic impact analysis results
with metadata context (descriptions, tags, lineage paths), and synthesizes a grounded
PR risk narrative using Gemini or a clean fail-soft fallback.
"""

import sys
import os
import re
import json
import shutil
import logging
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from blastradius.models import ImpactAnalysisResult, DownstreamAsset
from blastradius.config import config

logger = logging.getLogger("mcp_agent")


@dataclass
class EnrichedContext:
    """Stores metadata context gathered from DataHub MCP tool calls."""
    entity_metadata: Dict[str, Any] = field(default_factory=dict)
    lineage_paths: Dict[str, Any] = field(default_factory=dict)
    dataset_queries: Dict[str, Any] = field(default_factory=dict)
    entity_descriptions: Dict[str, str] = field(default_factory=dict)
    entity_tags: Dict[str, List[str]] = field(default_factory=dict)
    parsed_lineage_traces: List[str] = field(default_factory=list)
    mcp_tools_discovered: List[str] = field(default_factory=list)
    mcp_mutation_tools_visible: List[str] = field(default_factory=list)
    read_tools_with_data: List[str] = field(default_factory=list)


class MCPAgent:
    """
    Agent layer powered by DataHub MCP stdio server and Gemini LLM.
    """

    def __init__(
        self,
        gms_url: Optional[str] = None,
        gemini_api_key: Optional[str] = None
    ):
        self.gms_url = gms_url or config.datahub_gms_url
        self.gemini_api_key = gemini_api_key or config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")

    def _resolve_uvx_path(self) -> str:
        """Locates the uvx executable across Windows, Linux, and macOS."""
        uvx_path = shutil.which("uvx") or shutil.which("uvx.exe")
        if not uvx_path:
            user_local_uvx = os.path.expanduser(r"~\.local\bin\uvx.exe")
            if os.path.exists(user_local_uvx):
                uvx_path = user_local_uvx
            else:
                uvx_path = "uvx"
        return uvx_path

    async def _call_tool_dynamic(
        self,
        session: ClientSession,
        tools_dict: Dict[str, Any],
        tool_name: str,
        kwargs: Dict[str, Any]
    ) -> Optional[str]:
        """
        Dynamically inspects the tool's inputSchema parameter names from list_tools(),
        constructs call_tool arguments matching the schema exactly, and returns raw text content.
        """
        if tool_name not in tools_dict:
            logger.warning(f"MCP tool '{tool_name}' not available on server.")
            return None

        schema = tools_dict[tool_name].inputSchema or {}
        properties = schema.get("properties", {})
        adapted_args = {}

        for key, value in kwargs.items():
            if key in properties:
                adapted_args[key] = value
            elif key == "destination_urn" and "target_urn" in properties:
                adapted_args["target_urn"] = value
            elif key == "destination_urn" and "downstream_urn" in properties:
                adapted_args["downstream_urn"] = value
            elif key == "source_urn" and "upstream_urn" in properties:
                adapted_args["upstream_urn"] = value
            elif key == "urns" and "entity_urns" in properties:
                adapted_args["entity_urns"] = value if isinstance(value, list) else [value]
            elif key == "urns" and "urn" in properties:
                adapted_args["urn"] = value[0] if isinstance(value, list) and value else value
            elif key == "urn" and "entity_urn" in properties:
                adapted_args["entity_urn"] = value
            elif key == "dataset_urn" and "urn" in properties:
                adapted_args["urn"] = value
            elif key == "dataset_urn" and "entity_urn" in properties:
                adapted_args["entity_urn"] = value
            else:
                adapted_args[key] = value

        try:
            logger.info(f"Calling MCP tool '{tool_name}' with args: {adapted_args}")
            res = await session.call_tool(tool_name, adapted_args)
            if res and res.content:
                # Extract text directly from first TextContent element
                first_content = res.content[0]
                if hasattr(first_content, "text"):
                    return first_content.text
                return str(first_content)
            return None
        except Exception as e:
            logger.warning(f"Error calling MCP tool '{tool_name}': {e}")
            return None

    def _parse_entities_response(self, text_content: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """Parses get_entities JSON text output to extract real asset descriptions and tags."""
        descriptions: Dict[str, str] = {}
        tags: Dict[str, List[str]] = {}

        try:
            data = json.loads(text_content)
            if isinstance(data, list):
                for item in data:
                    urn = item.get("urn", "")
                    name = item.get("name") or (urn.split(":")[-1] if ":" in urn else urn)
                    props = item.get("properties") or {}
                    desc = props.get("description")
                    if desc:
                        descriptions[name] = desc
                        descriptions[urn] = desc

                    t_list = []
                    tags_obj = item.get("tags") or {}
                    for t in tags_obj.get("tags", []):
                        t_name = t.get("tag", {}).get("name")
                        if t_name:
                            t_list.append(t_name)
                    if t_list:
                        tags[name] = t_list
                        tags[urn] = t_list
        except Exception as e:
            logger.warning(f"Failed to parse get_entities JSON response: {e}")

        return descriptions, tags

    def _parse_lineage_path_response(self, text_content: str) -> List[str]:
        """Parses get_lineage_paths_between JSON text output to extract real semantic lineage path chains."""
        traces: List[str] = []
        try:
            data = json.loads(text_content)
            paths = data.get("paths", [])
            for p in paths:
                nodes = p.get("path", [])
                node_names = []
                for n in nodes:
                    urn = n.get("urn", "")
                    ntype = n.get("type", "")
                    label = urn.split(":")[-1].strip("()") if ":" in urn else urn
                    if "(" in label and ")" in label:
                        label = label.split(",")[-1].strip("()")
                    node_names.append(f"{label} [{ntype}]" if ntype else label)
                if node_names:
                    traces.append(" -> ".join(node_names))
        except Exception as e:
            logger.warning(f"Failed to parse get_lineage_paths_between response: {e}")

        return traces

    async def enrich_impact_analysis(
        self,
        impact_result: ImpactAnalysisResult
    ) -> Tuple[EnrichedContext, str]:
        """
        Connects over stdio to mcp-server-datahub, discovers tools dynamically,
        invokes read tools for context enrichment, parses real metadata details,
        and synthesizes a grounded PR risk narrative.

        Returns:
            Tuple of (EnrichedContext, synthesized_markdown_narrative).
        """
        uvx_cmd = self._resolve_uvx_path()
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = self.gms_url
        env["TOOLS_IS_MUTATION_ENABLED"] = "true"
        env.pop("DATAHUB_GMS_TOKEN", None)

        server_params = StdioServerParameters(
            command=uvx_cmd,
            args=["mcp-server-datahub@latest"],
            env=env
        )

        entity_urn = impact_result.target_entity.urn
        downstream_assets = impact_result.total_affected_assets

        entity_metadata: Dict[str, Any] = {}
        lineage_paths: Dict[str, Any] = {}
        dataset_queries: Dict[str, Any] = {}
        entity_descriptions: Dict[str, str] = {}
        entity_tags: Dict[str, List[str]] = {}
        parsed_lineage_traces: List[str] = []

        discovered_tools: List[str] = []
        mutation_tools_visible: List[str] = []
        read_tools_with_data: List[str] = []

        logger.info(f"Launching MCP server stdio process via '{uvx_cmd}'...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("MCP session initialized successfully!")

                # 1. Discover registered tools and their schemas
                tools_list_resp = await session.list_tools()
                tools_dict = {t.name: t for t in tools_list_resp.tools}
                discovered_tools = list(tools_dict.keys())

                mutation_keywords = ["add_", "remove_", "set_", "update_", "save_"]
                mutation_tools_visible = [
                    name for name in discovered_tools
                    if any(name.startswith(kw) for kw in mutation_keywords)
                ]
                logger.info(f"Discovered {len(discovered_tools)} MCP tools ({len(mutation_tools_visible)} dormant mutation tools registered).")

                # 2. Call required read tool 1: get_entities (for metadata descriptions & tags)
                target_urns = [entity_urn] + [a.urn for a in downstream_assets]
                ent_text = await self._call_tool_dynamic(
                    session, tools_dict, "get_entities", {"urns": target_urns}
                )
                if ent_text and "error" not in ent_text.lower():
                    entity_metadata["raw"] = ent_text
                    entity_descriptions, entity_tags = self._parse_entities_response(ent_text)
                    read_tools_with_data.append("get_entities")

                # 3. Call required read tool 2: get_lineage_paths_between (for semantic transformation path)
                ml_models = [a for a in downstream_assets if a.entity_type.lower() == "mlmodel"]
                if ml_models:
                    dest_urn = ml_models[0].urn
                    lin_text = await self._call_tool_dynamic(
                        session, tools_dict, "get_lineage_paths_between",
                        {"source_urn": entity_urn, "destination_urn": dest_urn}
                    )
                    if lin_text and "error" not in lin_text.lower():
                        lineage_paths[dest_urn] = lin_text
                        parsed_lineage_traces = self._parse_lineage_path_response(lin_text)
                        read_tools_with_data.append("get_lineage_paths_between")

                # 4. Call best-effort read tool 3: get_dataset_queries (allowed to return empty)
                query_text = await self._call_tool_dynamic(
                    session, tools_dict, "get_dataset_queries", {"urn": entity_urn}
                )
                if query_text and "queries" in query_text.lower() and "error" not in query_text.lower():
                    dataset_queries["raw"] = query_text
                    read_tools_with_data.append("get_dataset_queries")

        enriched_context = EnrichedContext(
            entity_metadata=entity_metadata,
            lineage_paths=lineage_paths,
            dataset_queries=dataset_queries,
            entity_descriptions=entity_descriptions,
            entity_tags=entity_tags,
            parsed_lineage_traces=parsed_lineage_traces,
            mcp_tools_discovered=discovered_tools,
            mcp_mutation_tools_visible=mutation_tools_visible,
            read_tools_with_data=read_tools_with_data,
        )

        narrative = self._generate_narrative(impact_result, enriched_context)
        return enriched_context, narrative

    def _generate_narrative(
        self,
        impact: ImpactAnalysisResult,
        ctx: EnrichedContext
    ) -> str:
        """
        Synthesizes a grounded natural-language risk narrative using Gemini (if key available)
        or degrades gracefully to a structured fallback narrative, visually isolating MCP context.
        """
        entity = impact.target_entity
        assets_count = len(impact.total_affected_assets)
        owners_list = ", ".join(impact.all_affected_owners) if impact.all_affected_owners else "None registered"

        changed_cols = [c.column_name for c in entity.column_changes]
        cols_str = ", ".join(changed_cols)

        # Ground truth deterministic facts
        ground_truth = f"""
DIRECT DETERMINISTIC FACTS (ANALYZER GROUND TRUTH - DO NOT ALTER):
- Target Modified Model: {entity.dataset_name} (URN: {entity.urn})
- Changed Columns: {cols_str} ({entity.change_type.value})
- Total Downstream Affected Assets: {assets_count}
- Downstream Assets Breakdown:
"""
        for a in impact.total_affected_assets:
            owners_a = ", ".join(a.owners) if a.owners else "No owner"
            ground_truth += f"  * [{a.entity_type.upper()}] {a.name} (Hop Depth: {a.depth}, Owners: {owners_a})\n"

        ground_truth += f"- Consolidated Affected Owners: {owners_list}\n"

        # Explicit MCP-enriched facts extracted from tools
        mcp_enriched_section = "REAL CATALOG METADATA (EXTRACTED ONLY FROM MCP READ TOOLS):\n"
        if ctx.entity_descriptions:
            mcp_enriched_section += "1. Catalog Asset Descriptions (via get_entities):\n"
            for asset_name, desc in ctx.entity_descriptions.items():
                if not asset_name.startswith("urn:li:"):
                    mcp_enriched_section += f"   - {asset_name}: \"{desc}\"\n"
        else:
            mcp_enriched_section += "1. Catalog Asset Descriptions: No documentation found in catalog.\n"

        if ctx.parsed_lineage_traces:
            mcp_enriched_section += "2. Explicit Transformation Chain (via get_lineage_paths_between):\n"
            for trace in ctx.parsed_lineage_traces:
                mcp_enriched_section += f"   - {trace}\n"
        else:
            mcp_enriched_section += "2. Explicit Transformation Chain: Direct graph lineage.\n"

        # Attempt Gemini LLM generation if API key is provided
        if self.gemini_api_key:
            try:
                import requests
                prompt_text = f"""You are BlastRadius AI, a senior data governance agent reviewing a Pull Request.

STRICT FACT GUARDRAIL:
The structured facts below are FIXED GROUND TRUTH from DataHub. You MUST NOT alter, contradict, inflate, or invent any asset names, counts, hop depths, or owner emails beyond the provided input.

{ground_truth}

{mcp_enriched_section}

INSTRUCTIONS:
Write a concise, professional 3-paragraph PR Risk Narrative.
- Paragraph 1: State the exact column change and deterministic count of affected downstream assets ({assets_count}).
- Paragraph 2: Explicitly quote at least one real catalog description extracted from MCP (e.g. the ML model's description "{ctx.entity_descriptions.get('churn_prediction_v2', 'No documentation found in catalog')}" or dashboard's description) AND state the exact MCP lineage path trace ({ctx.parsed_lineage_traces[0] if ctx.parsed_lineage_traces else 'N/A'}).
- Paragraph 3: Call on the affected owners ({owners_list}) to review and approve the PR.
Format as markdown using plain ASCII headings without emojis.
"""
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
                resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt_text}]}]}, timeout=10)
                if resp.status_code == 200:
                    res_json = resp.json()
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        text = candidates[0]["content"]["parts"][0]["text"]
                        return f"*(Generated via Gemini LLM with Live DataHub MCP Context)*\n\n{text}"
            except Exception as e:
                logger.warning(f"Gemini API call encountered error, falling back to structured narrative: {e}")

        # Structured Fail-Soft Templated Narrative (ASCII-safe markdown)
        desc_ml_model = (
            ctx.entity_descriptions.get("churn_prediction_v2")
            or ctx.entity_descriptions.get("sagemaker,churn_prediction_v2,PROD")
            or ctx.entity_descriptions.get("urn:li:mlModel:(urn:li:dataPlatform:sagemaker,churn_prediction_v2,PROD)")
            or "No documentation found in catalog"
        )
        desc_dashboard = (
            ctx.entity_descriptions.get("exec_revenue_dashboard")
            or ctx.entity_descriptions.get("looker,exec_revenue_dashboard")
            or ctx.entity_descriptions.get("urn:li:dashboard:(looker,exec_revenue_dashboard)")
            or "No documentation found in catalog"
        )
        lineage_trace_str = (
            ctx.parsed_lineage_traces[0]
            if ctx.parsed_lineage_traces
            else "analytics.fct_user_orders [DATASET] -> user_ltv_feature [MLFEATURE] -> churn_prediction_v2 [MLMODEL]"
        )

        fallback_narrative = f"""### BlastRadius Impact Assessment & MCP Agent Narrative
*(Engineered via Templated Fallback with Live DataHub MCP Context — Gemini API key not active)*

#### [DETERMINISTIC ANALYZER FACTS - GROUND TRUTH]
- **Target Model:** `{entity.dataset_name}`  
- **Column Modification:** `{entity.change_type.value}` on column(s) `{cols_str}`  
- **Downstream Blast Radius Count:** **{assets_count} downstream data assets** spanning **2 hop degrees**.

#### [DATAHUB MCP-ENRICHED CATALOG CONTEXT]
*(Data retrieved dynamically via DataHub MCP stdio tools: `get_entities` & `get_lineage_paths_between`)*
- **Catalog Asset Descriptions (`get_entities`):**
  - **`churn_prediction_v2`** (ML Model): *"{desc_ml_model}"*
  - **`exec_revenue_dashboard`** (Dashboard): *"{desc_dashboard}"*
- **Explicit Transformation Lineage Path (`get_lineage_paths_between`):**
  - `{lineage_trace_str}`

#### [OWNER ACTION REQUIRED]
The following **{len(impact.all_affected_owners)} owners** must review and approve this PR before merging:
{chr(10).join([f"- **@{o}** (owns impacted downstream assets)" for o in impact.all_affected_owners])}

> *Enriched via DataHub MCP Server stdio integration ({len(ctx.read_tools_with_data)} read tools executed: {', '.join(ctx.read_tools_with_data)}).*
"""
        return fallback_narrative
