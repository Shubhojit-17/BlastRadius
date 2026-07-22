"""
Analyzer Module.

Performs column-aware downstream blast radius impact analysis on ChangedEntity objects,
traversing multi-hop lineage and aggregating affected owners using the DataHubClient.
"""

import logging
from typing import List, Dict, Tuple, Optional, Set

from blastradius.models import (
    ChangedEntity,
    ColumnChange,
    DownstreamAsset,
    ColumnImpact,
    ImpactAnalysisResult,
)
from blastradius.datahub_client import DataHubClient, DataHubClientStub

logger = logging.getLogger("analyzer")


def aggregate_affected_owners(
    downstream_assets: List[DownstreamAsset]
) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Aggregates and deduplicates owners across a list of downstream assets,
    returning a deduplicated owner list and an owner -> asset URNs/names mapping.

    Args:
        downstream_assets: List of DownstreamAsset objects.

    Returns:
        Tuple of (deduplicated_owner_list, owner_to_assets_mapping).
    """
    owner_asset_map: Dict[str, List[str]] = {}
    deduped_owners_set: Set[str] = set()

    for asset in downstream_assets:
        asset_label = asset.name or asset.urn
        for owner in asset.owners:
            clean_owner = owner.replace("urn:li:corpuser:", "")
            deduped_owners_set.add(clean_owner)

            if clean_owner not in owner_asset_map:
                owner_asset_map[clean_owner] = []
            if asset_label not in owner_asset_map[clean_owner]:
                owner_asset_map[clean_owner].append(asset_label)

    return sorted(list(deduped_owners_set)), owner_asset_map


def analyze_impact(
    changed_entities: List[ChangedEntity],
    client: Optional[DataHubClient] = None
) -> List[ImpactAnalysisResult]:
    """
    Computes column-aware downstream blast radius and aggregates affected owners for each changed entity.

    Args:
        changed_entities: List of ChangedEntity objects (output from Resolver).
        client: DataHubClient instance (DataHubRestGraphClient or DataHubClientStub).

    Returns:
        List of ImpactAnalysisResult objects representing full blast radius assessments.
    """
    dh_client = client or DataHubClientStub()
    results: List[ImpactAnalysisResult] = []

    for entity in changed_entities:
        logger.info(f"Analyzing blast radius for entity: '{entity.dataset_name}' (URN: {entity.urn})")

        column_impacts: List[ColumnImpact] = []
        all_entity_assets: List[DownstreamAsset] = []
        seen_asset_urns: Set[str] = set()

        for col_change in entity.column_changes:
            logger.info(f"  --> Tracing downstream column lineage for '{col_change.column_name}' ({col_change.change_type.value})...")

            # Column-aware downstream traversal via DataHubClient
            col_assets = dh_client.fetch_downstream_column_lineage(
                entity_urn=entity.urn,
                column_name=col_change.column_name,
                max_depth=5
            )

            # Aggregate owners for this column change
            col_owners, _ = aggregate_affected_owners(col_assets)

            column_impacts.append(
                ColumnImpact(
                    column_name=col_change.column_name,
                    change_type=col_change.change_type,
                    affected_assets=col_assets,
                    affected_owners=col_owners,
                )
            )

            # Consolidate overall entity assets
            for asset in col_assets:
                if asset.urn not in seen_asset_urns:
                    all_entity_assets.append(asset)
                    seen_asset_urns.add(asset.urn)

        # Aggregate overall entity owners & mapping
        all_owners, owner_asset_map = aggregate_affected_owners(all_entity_assets)

        results.append(
            ImpactAnalysisResult(
                target_entity=entity,
                column_impacts=column_impacts,
                total_affected_assets=all_entity_assets,
                all_affected_owners=all_owners,
                owner_asset_map=owner_asset_map,
            )
        )

    return results
