"""
Contracts Module.

Retrieves DataHub data assertions and data contracts associated with target entities,
and evaluates whether PR schema/logic diffs violate contracts or break field rules.
"""

from typing import List, Optional
from blastradius.models import ChangedEntity, AssertionResult
from blastradius.datahub_client import DataHubClient


def fetch_entity_assertions(
    entity_urns: List[str],
    client: Optional[DataHubClient] = None
) -> List[AssertionResult]:
    """
    Retrieves active DataHub assertions and data contracts for given entity URNs
    using the DataHubClient interface.

    Args:
        entity_urns: List of modified DataHub dataset URNs.
        client: DataHubClient abstraction layer instance.

    Returns:
        List of AssertionResult objects attached to the entities.
    """
    pass


def evaluate_contract_impact(
    changed_entities: List[ChangedEntity],
    assertions: List[AssertionResult]
) -> List[AssertionResult]:
    """
    Evaluates whether PR diff changes (e.g. dropped columns, type changes) violate contracts.

    Args:
        changed_entities: List of changed entities with parsed diff details.
        assertions: Active DataHub assertions for those entities.

    Returns:
        Updated list of AssertionResult containing evaluation statuses and descriptions.
    """
    pass
