"""
Contracts and Assertions Module.

Evaluates column-aware DataHub data contracts and assertions against PR ColumnChange objects.
Determines whether attached data contracts are VIOLATED, UNAFFECTED, or AT_RISK with explicit
human-readable rationales.
"""

import logging
from typing import List, Optional

from blastradius.models import (
    ChangedEntity,
    ColumnChange,
    ChangeType,
    AssertionResult,
)
from blastradius.datahub_client import DataHubClient, DataHubClientStub

logger = logging.getLogger("contracts")


def evaluate_contracts(
    changed_entities: List[ChangedEntity],
    client: Optional[DataHubClient] = None
) -> List[AssertionResult]:
    """
    Evaluates column-aware data contracts and assertions attached to changed entities.

    Args:
        changed_entities: List of ChangedEntity objects from Resolver.
        client: DataHubClient instance.

    Returns:
        List of AssertionResult objects populated with status ('VIOLATED', 'UNAFFECTED', 'AT_RISK')
        and human-readable descriptions.
    """
    dh_client = client or DataHubClientStub()
    evaluated_results: List[AssertionResult] = []

    for entity in changed_entities:
        logger.info(f"Evaluating data contracts/assertions for entity '{entity.dataset_name}' (URN: {entity.urn})...")

        # Fetch assertions attached to dataset via DataHubClient
        assertions = dh_client.fetch_entity_assertions(entity.urn)
        if not assertions:
            logger.info(f"  --> No active contracts/assertions found for {entity.dataset_name}.")
            continue

        changed_col_names = {c.column_name: c for c in entity.column_changes}

        for assertion in assertions:
            protected_cols = assertion.protected_fields
            logger.info(f"  --> Evaluating assertion '{assertion.assertion_urn}' (Protected fields: {protected_cols})...")

            violating_change: Optional[ColumnChange] = None

            # Check if any changed column in PR targets a protected field
            if protected_cols:
                for p_col in protected_cols:
                    if p_col in changed_col_names:
                        violating_change = changed_col_names[p_col]
                        break

            if violating_change:
                # Column-aware VIOLATION detected!
                assertion.status = "VIOLATED"
                assertion.violating_column = violating_change.column_name
                assertion.description = (
                    f"Data contract assertion VIOLATED: Required column '{violating_change.column_name}' "
                    f"is {violating_change.change_type.value.lower()} by PR ({violating_change.description})."
                )
            elif protected_cols:
                # Assertion protects specific columns, but PR changed UNRELATED columns
                assertion.status = "UNAFFECTED"
                assertion.violating_column = None
                assertion.description = (
                    f"Data contract assertion UNAFFECTED: Protected column(s) {protected_cols} "
                    f"are not modified by PR column changes."
                )
            else:
                # Table-wide assertion without specific column scope (Speculative AT_RISK branch)
                assertion.status = "AT_RISK"
                assertion.violating_column = None
                assertion.description = (
                    f"Table-level assertion on {entity.dataset_name} marked AT_RISK due to SQL logic modification."
                )

            evaluated_results.append(assertion)

    return evaluated_results
