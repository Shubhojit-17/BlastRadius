"""
BlastRadius Core Orchestrator.

Wires the complete BlastRadius pipeline end-to-end:
SQL diff (base vs head) -> Resolver -> Analyzer -> Contracts -> MCP Agent -> Reporter -> Final AssessmentReport.
Returns AssessmentReport and exit code (non-zero when risk is HIGH).
"""

import logging
import asyncio
from typing import Tuple, Optional

from blastradius.models import AssessmentReport, RiskLevel
from blastradius.resolver import resolve_entities_from_sql_diff
from blastradius.analyzer import analyze_impact
from blastradius.contracts import evaluate_contracts
from blastradius.mcp_agent import MCPAgent, EnrichedContext
from blastradius.reporter import generate_pr_comment
from blastradius.datahub_client import DataHubClient, DataHubRestGraphClient, MockDataHubClient
from blastradius.config import config

logger = logging.getLogger("orchestrator")


def run_pipeline(
    base_sql: str,
    head_sql: str,
    client: Optional[DataHubClient] = None,
    use_mock: bool = False,
    pr_number: int = 1,
    commit_sha: str = "HEAD"
) -> Tuple[AssessmentReport, int]:
    """
    Executes the full BlastRadius analysis pipeline.

    Args:
        base_sql: SQL file content from base ref.
        head_sql: SQL file content from head PR ref.
        client: Optional DataHubClient instance (defaults to DataHubRestGraphClient or MockDataHubClient).
        use_mock: If True, uses MockDataHubClient and offline MCPAgent with recorded fixtures.
        pr_number: GitHub Pull Request number.
        commit_sha: Commit SHA under review.

    Returns:
        Tuple of (AssessmentReport, exit_code), where exit_code is 1 if RiskLevel is HIGH, else 0.
    """
    logger.info("=== Starting BlastRadius End-to-End Orchestrator Pipeline ===")

    # Select DataHubClient implementation
    if use_mock:
        dh_client = client or MockDataHubClient()
    else:
        try:
            dh_client = client or DataHubRestGraphClient(gms_url=config.datahub_gms_url, pat_token=config.datahub_pat_token)
        except Exception as e:
            logger.warning(f"Failed to connect to DataHub GMS, automatically falling back to MockDataHubClient: {e}")
            dh_client = MockDataHubClient()
            use_mock = True

    # Step 1: Resolver - Parse AST changes between base and head SQL
    logger.info("Step 1: Resolver - Resolving SQL diff changes...")
    changed_entities = resolve_entities_from_sql_diff(base_sql, head_sql, env="PROD", client=dh_client)
    if not changed_entities:
        logger.info("No entity or schema changes detected in SQL diff.")
        report = AssessmentReport(
            pr_number=pr_number,
            commit_sha=commit_sha,
            risk_level=RiskLevel.LOW,
            risk_score=0.0,
            changed_entities=[],
            downstream_impacts=[],
            contract_violations=[],
            summary_markdown="# 🛡️ BlastRadius PR Assessment: LOW RISK\n\n> ✅ **CI CHECK PASSED**: No schema modifications detected.",
        )
        return report, 0

    # Step 2: Analyzer - Compute column-aware downstream lineage impact
    logger.info("Step 2: Analyzer - Computing downstream column-level blast radius...")
    impact_results = analyze_impact(changed_entities, client=dh_client)

    # Step 3: Contracts - Evaluate column-aware DataHub contract violations
    logger.info("Step 3: Contracts - Evaluating DataHub data contract assertions...")
    contract_results = evaluate_contracts(changed_entities, client=dh_client)

    # Step 4: MCP Agent - Enrich with catalog descriptions & transformation trace
    logger.info("Step 4: MCP Agent - Enriching with DataHub MCP metadata context...")
    mcp_agent = MCPAgent(gms_url=config.datahub_gms_url)
    enriched_ctx, _ = asyncio.run(mcp_agent.enrich_impact_analysis(impact_results[0], use_mock=use_mock))

    # Step 5: Reporter - Generate transparent risk score and PR comment
    logger.info("Step 5: Reporter - Synthesizing final AssessmentReport...")
    report = generate_pr_comment(
        impact_results=impact_results,
        contract_results=contract_results,
        enriched_context=enriched_ctx,
        pr_number=pr_number,
        commit_sha=commit_sha,
    )

    exit_code = 1 if report.risk_level == RiskLevel.HIGH else 0
    logger.info(f"Pipeline Execution Complete. Risk Level: {report.risk_level.value} (Score: {report.risk_score:.1f}, Exit Code: {exit_code})")

    return report, exit_code
