"""
Resolver Module.

Parses SQL/dbt diff files and full before/after model files from GitHub Pull Requests using SQLGlot,
performing source-expression-based AST matching to identify column drops, renames, additions,
and data type changes, then resolving models to canonical DataHub dataset URNs.
"""

import os
import re
import logging
from typing import List, Optional, Tuple, Dict, Any
import sqlglot

from blastradius.models import ChangedEntity, ColumnChange, ChangeType
from blastradius.datahub_client import DataHubClient, DataHubClientStub

logger = logging.getLogger("resolver")


def clean_dbt_sql(sql_content: str) -> str:
    """Strips Jinja template tags (e.g. {{ ref('table') }}, {{ config(...) }}) so SQLGlot can parse standard SQL."""
    # Replace {{ ref('model') }} or {{ source('schema', 'table') }} with table name
    cleaned = re.sub(r"\{\{\s*ref\(['\"](\w+)['\"]\)\s*\}\}", r"\1", sql_content)
    cleaned = re.sub(r"\{\{\s*source\(['\"](\w+)['\"]\s*,\s*['\"](\w+)['\"]\)\s*\}\}", r"\2", cleaned)
    # Remove {{ config(...) }} blocks
    cleaned = re.sub(r"\{\{\s*config\(.*?\)\s*\}\}", "", cleaned, flags=re.DOTALL)
    # Remove Jinja comments and block tags
    cleaned = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\{%.*?%\}", "", cleaned)
    return cleaned


def extract_columns_with_expressions(sql_code: str, dialect: str = "snowflake") -> Dict[str, Dict[str, Any]]:
    """
    Parses SQL code using SQLGlot and extracts projected columns with their underlying source expressions.

    Returns:
        Dict mapping output_column_name -> {
            "source_expr": str,
            "output_name": str,
            "cast_type": str
        }
    """
    cleaned = clean_dbt_sql(sql_code)
    try:
        ast = sqlglot.parse_one(cleaned, read=dialect)
        if not ast or not hasattr(ast, "selects"):
            return {}

        results = {}
        for select in ast.selects:
            output_name = select.alias_or_name

            # Determine underlying source expression
            if isinstance(select, sqlglot.exp.Alias):
                source_expr = select.this.sql(dialect=dialect)
            else:
                source_expr = select.sql(dialect=dialect)

            # Determine explicit cast type if present
            cast_type = "UNKNOWN"
            if isinstance(select, sqlglot.exp.Alias) and isinstance(select.this, sqlglot.exp.Cast) and hasattr(select.this, "to"):
                cast_type = str(select.this.to)
            elif isinstance(select, sqlglot.exp.Cast) and hasattr(select, "to"):
                cast_type = str(select.to)

            results[output_name] = {
                "source_expr": source_expr,
                "output_name": output_name,
                "cast_type": cast_type,
            }
        return results
    except Exception as e:
        logger.warning(f"SQLGlot parsing error: {e}")
        return {}


def parse_sql_file_diff(
    old_file_content: str,
    new_file_content: str,
    model_name: str,
    dialect: str = "snowflake"
) -> ChangedEntity:
    """
    Primary Path: Parses complete old and new SQL file content using SQLGlot,
    performing source-expression-based AST comparison.
    """
    old_cols = extract_columns_with_expressions(old_file_content, dialect=dialect)
    new_cols = extract_columns_with_expressions(new_file_content, dialect=dialect)

    old_expr_map = {info["source_expr"]: info for info in old_cols.values()}
    new_expr_map = {info["source_expr"]: info for info in new_cols.values()}

    column_changes: List[ColumnChange] = []
    processed_old_names = set()
    processed_new_names = set()

    # 1. Match by Output Name first (Same column output name, check type or expression modifications)
    for col_name, old_info in old_cols.items():
        if col_name in new_cols:
            new_info = new_cols[col_name]
            processed_old_names.add(col_name)
            processed_new_names.add(col_name)

            # Detect data type change on same output column name
            if old_info["cast_type"] != new_info["cast_type"]:
                column_changes.append(
                    ColumnChange(
                        column_name=col_name,
                        change_type=ChangeType.COLUMN_TYPE_CHANGE,
                        old_type=old_info["cast_type"],
                        new_type=new_info["cast_type"],
                        description=f"Modified data type of '{col_name}' from {old_info['cast_type']} to {new_info['cast_type']}"
                    )
                )

    # 2. Match by Source Expression (Renamed columns: source expression matches, output name differs)
    for source_expr, old_info in old_expr_map.items():
        old_name = old_info["output_name"]
        if old_name in processed_old_names:
            continue

        if source_expr in new_expr_map:
            new_info = new_expr_map[source_expr]
            new_name = new_info["output_name"]

            if new_name not in processed_new_names:
                column_changes.append(
                    ColumnChange(
                        column_name=old_name,
                        change_type=ChangeType.COLUMN_RENAME,
                        old_name=old_name,
                        new_name=new_name,
                        description=f"Renamed column '{old_name}' to '{new_name}' (source expression: {source_expr})"
                    )
                )
                processed_old_names.add(old_name)
                processed_new_names.add(new_name)

    # 3. True Column Drops (Old column/expression missing in new AST)
    for old_name, old_info in old_cols.items():
        if old_name not in processed_old_names and old_info["source_expr"] not in new_expr_map:
            column_changes.append(
                ColumnChange(
                    column_name=old_name,
                    change_type=ChangeType.COLUMN_DROP,
                    old_name=old_name,
                    description=f"Dropped column '{old_name}' from {model_name}"
                )
            )

    # 4. True Column Additions (New column/expression missing in old AST)
    for new_name, new_info in new_cols.items():
        if new_name not in processed_new_names and new_info["source_expr"] not in old_expr_map:
            column_changes.append(
                ColumnChange(
                    column_name=new_name,
                    change_type=ChangeType.COLUMN_ADD,
                    new_name=new_name,
                    description=f"Added column '{new_name}' to {model_name}"
                )
            )

    # High level change type
    entity_change_type = ChangeType.SQL_LOGIC_MODIFIED
    if any(c.change_type == ChangeType.COLUMN_DROP for c in column_changes):
        entity_change_type = ChangeType.COLUMN_DROP
    elif any(c.change_type == ChangeType.COLUMN_RENAME for c in column_changes):
        entity_change_type = ChangeType.COLUMN_RENAME

    return ChangedEntity(
        urn="",  # Populated in resolve_entities_to_urns
        dataset_name=model_name,
        change_type=entity_change_type,
        column_changes=column_changes,
        raw_diff=f"Full file parse for model {model_name}",
    )


def parse_pr_diff(
    diff_content: Optional[str] = None,
    file_contents: Optional[Dict[str, Tuple[str, str]]] = None,
    dialect: str = "snowflake"
) -> List[ChangedEntity]:
    """
    Dual-path PR diff parser.

    Args:
        diff_content: Optional git patch text string.
        file_contents: Optional Dict mapping file_path -> (old_file_content, new_file_content).
        dialect: SQLGlot SQL dialect name.

    Returns:
        List of ChangedEntity instances identified in the diff.
    """
    changed_entities: List[ChangedEntity] = []

    # PRIMARY PATH: Parse full before/after file contents if provided
    if file_contents:
        logger.info("Using Primary Path: Parsing full before/after SQL file contents")
        for file_path, (old_content, new_content) in file_contents.items():
            if not file_path.endswith(".sql"):
                continue
            model_name = os.path.basename(file_path).replace(".sql", "")
            entity = parse_sql_file_diff(old_content, new_content, model_name=model_name, dialect=dialect)
            changed_entities.append(entity)
        return changed_entities

    # FALLBACK PATH: Reconstruct old/new SQL from git patch hunks
    if diff_content:
        logger.warning("Using Fallback Path: Reconstructing SQL from git patch hunks (full file blobs absent)")
        file_diffs = re.split(r"^diff --git ", diff_content, flags=re.MULTILINE)
        for file_diff in file_diffs:
            if not file_diff.strip():
                continue

            match_path = re.search(r"\+\+\+ b/(.+)$", file_diff, flags=re.MULTILINE)
            if not match_path:
                continue

            file_path = match_path.group(1).strip()
            if not file_path.endswith(".sql"):
                continue

            model_name = os.path.basename(file_path).replace(".sql", "")

            old_lines = []
            new_lines = []
            for line in file_diff.splitlines():
                stripped = line.strip()
                if (
                    line.startswith("---")
                    or line.startswith("+++")
                    or line.startswith("@@")
                    or line.startswith("index")
                    or line.startswith("diff")
                    or re.match(r"^a/.+ b/.+", stripped)
                ):
                    continue

                if line.startswith("-"):
                    old_lines.append(line[1:])
                elif line.startswith("+"):
                    new_lines.append(line[1:])
                else:
                    old_lines.append(line)
                    new_lines.append(line)

            old_sql = "\n".join(old_lines)
            new_sql = "\n".join(new_lines)

            entity = parse_sql_file_diff(old_sql, new_sql, model_name=model_name, dialect=dialect)
            entity.raw_diff = file_diff
            changed_entities.append(entity)

    return changed_entities


def resolve_entities_to_urns(
    entities: List[ChangedEntity],
    env: str = "PROD",
    client: Optional[DataHubClient] = None
) -> List[ChangedEntity]:
    """
    Maps dataset/table names extracted from SQL diffs to canonical DataHub URNs
    using the DataHubClient interface.

    Args:
        entities: Unresolved list of ChangedEntity objects.
        env: Target DataHub environment string (e.g. 'PROD', 'DEV').
        client: DataHubClient instance.

    Returns:
        List of ChangedEntity objects updated with populated DataHub URNs.
    """
    dh_client = client or DataHubClientStub()
    resolved_entities: List[ChangedEntity] = []

    for entity in entities:
        urn = dh_client.resolve_entity_urn(entity.dataset_name, env=env)
        if not urn:
            urn = f"urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.{entity.dataset_name},{env})"

        entity.urn = urn
        resolved_entities.append(entity)

    return resolved_entities


def resolve_entities_from_sql_diff(
    base_sql: str,
    head_sql: str,
    model_name: str = "fct_user_orders",
    env: str = "PROD",
    client: Optional[DataHubClient] = None
) -> List[ChangedEntity]:
    """
    Convenience helper: parses base and head SQL file contents using SQLGlot,
    detects AST column changes, and resolves URNs against DataHub.
    """
    unresolved = parse_pr_diff(file_contents={f"models/{model_name}.sql": (base_sql, head_sql)})
    return resolve_entities_to_urns(unresolved, env=env, client=client)

