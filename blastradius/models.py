"""
BlastRadius Core Data Models.

Defines the column-aware data structures used across resolver, analyzer, contracts,
reporter, writeback, and orchestrator modules.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class RiskLevel(Enum):
    """Enumeration of risk levels assigned to a PR blast radius assessment."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeType(Enum):
    """Types of schema or SQL changes identified in PR diffs."""
    TABLE_CREATE = "TABLE_CREATE"
    TABLE_DROP = "TABLE_DROP"
    COLUMN_ADD = "COLUMN_ADD"
    COLUMN_DROP = "COLUMN_DROP"
    COLUMN_RENAME = "COLUMN_RENAME"
    COLUMN_TYPE_CHANGE = "COLUMN_TYPE_CHANGE"
    SQL_LOGIC_MODIFIED = "SQL_LOGIC_MODIFIED"


@dataclass
class ColumnChange:
    """
    Represents a specific column-level change within an entity.

    Attributes:
        column_name: Name of column being modified or dropped.
        change_type: Specific change type for this column.
        old_name: Original column name if renamed.
        new_name: New column name if renamed.
        old_type: Original data type if changed.
        new_type: New data type if changed.
        description: Additional change details or diff snippet.
    """
    column_name: str
    change_type: ChangeType
    old_name: Optional[str] = None
    new_name: Optional[str] = None
    old_type: Optional[str] = None
    new_type: Optional[str] = None
    description: str = ""


@dataclass
class ChangedEntity:
    """
    Represents a dataset or view altered within a PR diff with column-level details.

    Attributes:
        urn: DataHub canonical URN (e.g. urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.table,PROD)).
        dataset_name: Fully qualified dataset/table name extracted from code.
        change_type: High-level modification type for the dataset.
        column_changes: Granular list of column-level modifications.
        raw_diff: Snippet of raw git diff context associated with entity.
    """
    urn: str
    dataset_name: str
    change_type: ChangeType
    column_changes: List[ColumnChange] = field(default_factory=list)
    raw_diff: str = ""


@dataclass
class ColumnLineagePath:
    """
    Tracks column-level connection path from an upstream column to a downstream column/asset.

    Attributes:
        upstream_urn: Canonical URN of upstream dataset/entity.
        upstream_column: Name of upstream column.
        downstream_urn: Canonical URN of downstream dataset/asset.
        downstream_column: Name of downstream column or field.
    """
    upstream_urn: str
    upstream_column: str
    downstream_urn: str
    downstream_column: str


@dataclass
class DownstreamAsset:
    """
    Represents a downstream entity discovered via DataHub column/dataset lineage traversal.

    Attributes:
        urn: Canonical DataHub URN of downstream entity.
        name: Display name or identifier of asset.
        entity_type: DataHub entity category (e.g., 'dataset', 'dashboard', 'chart', 'mlFeature').
        depth: Hop distance downstream from modified root dataset.
        column_paths: Column-level lineage traces connecting upstream changed column to downstream asset.
        owners: List of owner names/emails registered in DataHub.
    """
    urn: str
    name: str
    entity_type: str
    depth: int
    column_paths: List[ColumnLineagePath] = field(default_factory=list)
    owners: List[str] = field(default_factory=list)


@dataclass
class AssertionResult:
    """
    Represents the evaluation status of a DataHub assertion or contract.

    Attributes:
        assertion_urn: Canonical URN of assertion in DataHub.
        entity_urn: Target dataset URN attached to assertion.
        assertion_type: Category of assertion (e.g., 'freshness', 'schema', 'custom').
        status: Evaluation verdict ('PASSED', 'FAILED', 'POTENTIALLY_BROKEN').
        description: Human-readable rationale or failure description.
    """
    assertion_urn: str
    entity_urn: str
    assertion_type: str
    status: str
    description: str


@dataclass
class ColumnImpact:
    """
    Stores impact details for a single changed column within an entity.

    Attributes:
        column_name: Name of column being modified/dropped.
        change_type: Column ChangeType.
        affected_assets: List of downstream assets specifically impacted by this column.
        affected_owners: Deduplicated list of owners of the affected assets.
    """
    column_name: str
    change_type: ChangeType
    affected_assets: List[DownstreamAsset] = field(default_factory=list)
    affected_owners: List[str] = field(default_factory=list)


@dataclass
class ImpactAnalysisResult:
    """
    Complete impact analysis result for a changed entity.

    Attributes:
        target_entity: The ChangedEntity evaluated.
        column_impacts: Per-column impact breakdown.
        total_affected_assets: Consolidated list of all affected downstream assets.
        all_affected_owners: Consolidated list of all affected owners.
        owner_asset_map: Mapping of owner_identifier -> list of affected asset URNs/names owned.
    """
    target_entity: ChangedEntity
    column_impacts: List[ColumnImpact] = field(default_factory=list)
    total_affected_assets: List[DownstreamAsset] = field(default_factory=list)
    all_affected_owners: List[str] = field(default_factory=list)
    owner_asset_map: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class AssessmentReport:
    """
    Comprehensive final report aggregating PR blast radius evaluation metrics.

    Attributes:
        pr_number: GitHub Pull Request ID.
        commit_sha: Git commit SHA analyzed.
        risk_level: Assigned RiskLevel enum.
        risk_score: Numerical risk score (0.0 to 100.0).
        changed_entities: List of entities directly modified in PR diff.
        downstream_impacts: List of downstream assets discovered via lineage.
        contract_violations: List of assertion/contract evaluation results.
        summary_markdown: Markdown formatted verdict summary for PR comment.
    """
    pr_number: int
    commit_sha: str
    risk_level: RiskLevel
    risk_score: float
    changed_entities: List[ChangedEntity]
    downstream_impacts: List[DownstreamAsset]
    contract_violations: List[AssertionResult]
    summary_markdown: str = ""
