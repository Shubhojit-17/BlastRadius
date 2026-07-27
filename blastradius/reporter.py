"""
Reporter and Transparent Risk Scoring Module.

Calculates transparent, auditable PR risk scores and generates formatted GitHub PR Assessment comments.
Applies hard override rule: any VIOLATED contract forces RiskLevel.HIGH.
"""

import logging
from typing import List, Dict, Tuple, Optional

from blastradius.models import (
    RiskLevel,
    ImpactAnalysisResult,
    AssertionResult,
    AssessmentReport,
    DownstreamAsset,
)
from blastradius.mcp_agent import EnrichedContext

logger = logging.getLogger("reporter")


def calculate_risk_score(
    impact_results: List[ImpactAnalysisResult],
    contract_results: List[AssertionResult]
) -> Tuple[RiskLevel, float, List[str], str]:
    """
    Computes a transparent, auditable risk score and assigns a RiskLevel enum.

    Rubric Weights:
    - Violated Data Contract: +50.0 pts per broken contract
    - Downstream Production ML Model: +25.0 pts
    - Downstream Assets: +5.0 pts per asset
    - Multi-Hop Depth: +5.0 pts per hop depth > 1
    - Cross-Team Owners: +5.0 pts per additional owner > 1

    Hard Override Rule:
    Any VIOLATED contract FORCES RiskLevel.HIGH regardless of numeric score.

    Returns:
        Tuple of (RiskLevel, capped_score, score_breakdown_lines, rationale_summary).
    """
    raw_score = 0.0
    breakdown: List[str] = []

    # 1. Evaluate Contract Violations
    violated_contracts = [a for a in contract_results if a.status == "VIOLATED"]
    if violated_contracts:
        pts = len(violated_contracts) * 50.0
        raw_score += pts
        breakdown.append(f"`+{pts:.1f} pts` -- {len(violated_contracts)} Violated Data Contract(s) ({', '.join([c.assertion_urn.split(':')[-1] for c in violated_contracts])})")

    # 2. Evaluate Downstream Assets & ML Models
    all_affected_assets: List[DownstreamAsset] = []
    all_owners: set = set()
    has_ml_model = False
    max_depth = 1

    for imp in impact_results:
        for asset in imp.total_affected_assets:
            if asset not in all_affected_assets:
                all_affected_assets.append(asset)
            if asset.depth > max_depth:
                max_depth = asset.depth
            if asset.entity_type.lower() == "mlmodel":
                has_ml_model = True
            for o in asset.owners:
                all_owners.add(o)

    if has_ml_model:
        raw_score += 25.0
        breakdown.append("`+25.0 pts` -- Production ML Model in downstream lineage")

    if all_affected_assets:
        pts = len(all_affected_assets) * 5.0
        raw_score += pts
        breakdown.append(f"`+{pts:.1f} pts` -- {len(all_affected_assets)} Downstream Affected Asset(s) (5.0 pts / asset)")

    if max_depth > 1:
        pts = (max_depth - 1) * 5.0
        raw_score += pts
        breakdown.append(f"`+{pts:.1f} pts` -- Multi-Hop Lineage Depth {max_depth}")

    if len(all_owners) > 1:
        pts = (len(all_owners) - 1) * 5.0
        raw_score += pts
        breakdown.append(f"`+{pts:.1f} pts` -- {len(all_owners)} Cross-Team Owners Affected")

    if not breakdown:
        breakdown.append("`+0.0 pts` -- No downstream assets or contract violations detected")

    capped_score = min(100.0, raw_score)

    # Apply Hard Override & Threshold Rules
    if violated_contracts:
        risk_level = RiskLevel.HIGH
        rationale = f"HIGH RISK (Hard Override: {len(violated_contracts)} violated data contract(s))"
    elif capped_score >= 50.0:
        risk_level = RiskLevel.HIGH
        rationale = f"HIGH RISK (Score {capped_score:.1f}/100 >= 50.0 threshold)"
    elif capped_score >= 30.0:
        risk_level = RiskLevel.MEDIUM
        rationale = f"MEDIUM RISK (Score {capped_score:.1f}/100 >= 30.0 threshold)"
    else:
        risk_level = RiskLevel.LOW
        rationale = f"LOW RISK (Score {capped_score:.1f}/100 < 30.0 threshold)"

    return risk_level, capped_score, breakdown, rationale


def generate_pr_comment(
    impact_results: List[ImpactAnalysisResult],
    contract_results: List[AssertionResult],
    enriched_context: EnrichedContext,
    pr_number: int = 1,
    commit_sha: str = "HEAD"
) -> AssessmentReport:
    """
    Generates a comprehensive Markdown PR comment report.
    """
    risk_level, score, breakdown, rationale = calculate_risk_score(impact_results, contract_results)

    violated_contracts = [a for a in contract_results if a.status == "VIOLATED"]
    unaffected_contracts = [a for a in contract_results if a.status == "UNAFFECTED"]

    all_assets: List[DownstreamAsset] = []
    all_owners: List[str] = []
    for imp in impact_results:
        for a in imp.total_affected_assets:
            if a not in all_assets:
                all_assets.append(a)
        for o in imp.all_affected_owners:
            if o not in all_owners:
                all_owners.append(o)

    target_entity = impact_results[0].target_entity if impact_results else None
    dataset_name = target_entity.dataset_name if target_entity else "unknown_dataset"
    changed_cols = [c.column_name for c in target_entity.column_changes] if target_entity else []
    change_type = target_entity.change_type.value if target_entity else "MODIFIED"

    # 1. Header Banner
    if risk_level == RiskLevel.HIGH:
        banner = "# 🛡️ BlastRadius PR Assessment: HIGH RISK\n\n> ⚠️ **CI CHECK FAILED**: High-risk schema/contract changes detected. Review from affected owners required."
    elif risk_level == RiskLevel.MEDIUM:
        banner = "# 🛡️ BlastRadius PR Assessment: MEDIUM RISK\n\n> ⚡ **CI CHECK PASSED WITH WARNINGS**: Moderate blast radius detected."
    else:
        banner = "# 🛡️ BlastRadius PR Assessment: LOW RISK\n\n> ✅ **CI CHECK PASSED**: Safe schema change with minimal downstream impact."

    markdown = f"{banner}\n\n---\n\n"

    # 2. Broken Contract Callout Section
    if violated_contracts:
        markdown += "### 🚨 Broken Data Contracts & Assertions\n"
        for vc in violated_contracts:
            c_name = vc.assertion_urn.split(":")[-1]
            markdown += f"> 💥 **CONTRACT VIOLATION:** This PR violates data contract `{c_name}`!\n"
            markdown += f"> **Reason:** {vc.description}\n\n"
        markdown += "---\n\n"

    # 3. Deterministic Impact Summary
    markdown += "### 📊 Deterministic Impact Summary\n"
    markdown += f"- **Target Model:** `{dataset_name}`\n"
    markdown += f"- **Change Type:** `{change_type}` on column(s) `{', '.join(changed_cols)}`\n"
    markdown += f"- **Risk Verdict:** **{risk_level.value} RISK** (Score: `{score:.1f}/100.0`)\n"
    markdown += f"- **Primary Rationale:** {rationale}\n\n"

    markdown += "#### Auditable Score Arithmetic Breakdown\n"
    for line in breakdown:
        markdown += f"- {line}\n"
    markdown += "\n"

    # 4. Downstream Assets Table
    if all_assets:
        markdown += f"#### Downstream Affected Assets ({len(all_assets)} Total, Max Hop Depth: {max([a.depth for a in all_assets])})\n"
        markdown += "| Asset Type | Asset Name | Hop Depth | Registered Owners |\n"
        markdown += "| :--- | :--- | :---: | :--- |\n"
        type_icons = {"chart": "📊 `CHART`", "dashboard": "📈 `DASHBOARD`", "mlfeature": "🧪 `MLFEATURE`", "mlmodel": "🤖 `MLMODEL`", "dataset": "🗄️ `DATASET`"}
        for a in all_assets:
            icon = type_icons.get(a.entity_type.lower(), f"`{a.entity_type.upper()}`")
            owners_str = ", ".join([f"`@{o.split(':')[-1]}`" for o in a.owners]) if a.owners else "No owner"
            markdown += f"| {icon} | `{a.name}` | {a.depth} | {owners_str} |\n"
        markdown += "\n"

    # 5. Owners List
    if all_owners:
        markdown += "#### 👥 Action Required from Owners\n"
        markdown += f"The following **{len(all_owners)} owners** must review and approve this PR:\n"
        for o in all_owners:
            markdown += f"- **@{o}** (owns impacted downstream assets)\n"
        markdown += "\n"

    # 6. MCP-Enriched Context
    markdown += "---\n\n"
    markdown += "### 🔍 DataHub MCP-Enriched Catalog Context\n"

    if not all_assets:
        col_str = ", ".join(changed_cols) if changed_cols else "specified column"
        markdown += f"*No downstream assets are affected by this column change — column-level lineage confirms `{col_str}` has no dependents.*\n"
    else:
        markdown += f"*(Retrieved via DataHub MCP stdio tools: {', '.join(enriched_context.read_tools_with_data) if enriched_context.read_tools_with_data else 'Offline Mock Fixtures'})*\n\n"

        affected_asset_names = {a.name for a in all_assets}
        affected_asset_names.add(dataset_name)

        filtered_descriptions = {
            name: desc for name, desc in enriched_context.entity_descriptions.items()
            if not name.startswith("urn:li:") and (name in affected_asset_names or any(an in name for an in affected_asset_names))
        }

        if filtered_descriptions:
            markdown += "- **Catalog Descriptions (`get_entities`):**\n"
            for name, desc in filtered_descriptions.items():
                markdown += f"  - **`{name}`**: *\"{desc}\"*\n"
        else:
            markdown += "- **Catalog Descriptions:** No documentation found in catalog.\n"

        if enriched_context.parsed_lineage_traces:
            markdown += "- **Explicit Lineage Path (`get_lineage_paths_between`):**\n"
            for trace in enriched_context.parsed_lineage_traces:
                markdown += f"  - `{trace}`\n"
        else:
            markdown += "- **Explicit Lineage Path:** Direct graph lineage.\n"

    changed_entities = [imp.target_entity for imp in impact_results]

    return AssessmentReport(
        pr_number=pr_number,
        commit_sha=commit_sha,
        risk_level=risk_level,
        risk_score=score,
        changed_entities=changed_entities,
        downstream_impacts=all_assets,
        contract_violations=violated_contracts,
        summary_markdown=markdown,
    )
