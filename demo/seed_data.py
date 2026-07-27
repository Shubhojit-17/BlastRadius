"""
Demo Data Stack Seeder for DataHub.

Ingests a realistic, breakable demo data stack into DataHub using the acryl-datahub SDK:
- 2 raw source tables (raw_postgres.public.users, raw_postgres.public.orders)
- 1 derived model (snowflake.analytics.fct_user_orders)
- Column-level lineage connecting order_amount -> lifetime_value
- 1 Looker Chart & Dashboard built on the derived table
- ML Layer: ML Feature (user_ltv_feature), ML Feature Table (user_churn_features), and ML Model (churn_prediction_v2)
- 1 Data Contract / Schema Assertion attached to fct_user_orders
- Ownership metadata for all key assets
"""

import sys
import time
import logging
from typing import List, Any

from datahub.emitter.rest_emitter import DataHubRestEmitter
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass,
    SchemaMetadataClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    StringTypeClass,
    NumberTypeClass,
    TimeTypeClass,
    UpstreamLineageClass,
    UpstreamClass,
    FineGrainedLineageClass,
    FineGrainedLineageDownstreamTypeClass,
    FineGrainedLineageUpstreamTypeClass,
    DatasetLineageTypeClass,
    ChartInfoClass,
    DashboardInfoClass,
    AuditStampClass,
    ChangeAuditStampsClass,
    OwnershipClass,
    OwnerClass,
    OwnershipTypeClass,
    MLFeaturePropertiesClass,
    MLFeatureDataTypeClass,
    MLFeatureTablePropertiesClass,
    MLModelPropertiesClass,
    AssertionInfoClass,
    AssertionTypeClass,
    DatasetAssertionInfoClass,
    DatasetAssertionScopeClass,
    AssertionStdOperatorClass,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_data")

GMS_ENDPOINT = "http://localhost:8080"

# Entity URN Definitions
URN_USERS_RAW = "urn:li:dataset:(urn:li:dataPlatform:postgres,raw_postgres.public.users,PROD)"
URN_ORDERS_RAW = "urn:li:dataset:(urn:li:dataPlatform:postgres,raw_postgres.public.orders,PROD)"
URN_FCT_USER_ORDERS = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_user_orders,PROD)"

URN_FIELD_LTV = f"urn:li:schemaField:({URN_FCT_USER_ORDERS},lifetime_value)"

URN_CHART_REVENUE = "urn:li:chart:(looker,user_revenue_chart)"
URN_DASHBOARD_EXEC = "urn:li:dashboard:(looker,exec_revenue_dashboard)"

URN_ML_FEATURE_LTV = "urn:li:mlFeature:(sagemaker,user_ltv_feature)"
URN_ML_FEATURES = "urn:li:mlFeatureTable:(urn:li:dataPlatform:sagemaker,user_churn_features)"
URN_ML_MODEL = "urn:li:mlModel:(urn:li:dataPlatform:sagemaker,churn_prediction_v2,PROD)"

URN_ASSERTION_LTV = "urn:li:assertion:fct_user_orders_ltv_schema"


def create_schema_field(field_path: str, native_type: str, type_class: Any) -> SchemaFieldClass:
    """Helper to create a SchemaFieldClass instance."""
    return SchemaFieldClass(
        fieldPath=field_path,
        type=SchemaFieldDataTypeClass(type=type_class),
        nativeDataType=native_type,
        description=f"Field {field_path}"
    )


def create_ownership(owner_email: str, ownership_type: Any = OwnershipTypeClass.TECHNICAL_OWNER) -> OwnershipClass:
    """Helper to create an OwnershipClass instance."""
    return OwnershipClass(
        owners=[
            OwnerClass(
                owner=f"urn:li:corpuser:{owner_email}",
                type=ownership_type,
            )
        ]
    )


def emit_metadata(emitter: DataHubRestEmitter) -> None:
    """Emits all MCPs to DataHub GMS."""
    mcps: List[MetadataChangeProposalWrapper] = []

    now_ms = int(time.time() * 1000)
    audit_stamp = AuditStampClass(time=now_ms, actor="urn:li:corpuser:datahub")
    change_audit_stamps = ChangeAuditStampsClass(created=audit_stamp, lastModified=audit_stamp)

    # 1. Raw Users Source Dataset Schema
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_USERS_RAW,
            aspect=DatasetPropertiesClass(description="Raw user registration table in Postgres"),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_USERS_RAW,
            aspect=SchemaMetadataClass(
                schemaName="raw_users",
                platform="urn:li:dataPlatform:postgres",
                version=0,
                hash="",
                platformSchema=StringTypeClass(),
                fields=[
                    create_schema_field("user_id", "INT", NumberTypeClass()),
                    create_schema_field("email", "VARCHAR", StringTypeClass()),
                    create_schema_field("signup_timestamp", "TIMESTAMP", TimeTypeClass()),
                ],
            ),
        )
    )

    # 2. Raw Orders Source Dataset Schema
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ORDERS_RAW,
            aspect=DatasetPropertiesClass(description="Raw order transactions table in Postgres"),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ORDERS_RAW,
            aspect=SchemaMetadataClass(
                schemaName="raw_orders",
                platform="urn:li:dataPlatform:postgres",
                version=0,
                hash="",
                platformSchema=StringTypeClass(),
                fields=[
                    create_schema_field("order_id", "INT", NumberTypeClass()),
                    create_schema_field("user_id", "INT", NumberTypeClass()),
                    create_schema_field("order_amount", "DECIMAL", NumberTypeClass()),
                    create_schema_field("status", "VARCHAR", StringTypeClass()),
                    create_schema_field("created_at", "TIMESTAMP", TimeTypeClass()),
                ],
            ),
        )
    )

    # 3. Transformation Layer: fct_user_orders Schema & Column-Level Lineage & Ownership
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_FCT_USER_ORDERS,
            aspect=DatasetPropertiesClass(description="Derived dbt model for user lifetime value and order metrics"),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_FCT_USER_ORDERS,
            aspect=SchemaMetadataClass(
                schemaName="fct_user_orders",
                platform="urn:li:dataPlatform:snowflake",
                version=0,
                hash="",
                platformSchema=StringTypeClass(),
                fields=[
                    create_schema_field("user_id", "INT", NumberTypeClass()),
                    create_schema_field("user_email", "VARCHAR", StringTypeClass()),
                    create_schema_field("total_orders", "INT", NumberTypeClass()),
                    create_schema_field("lifetime_value", "DECIMAL", NumberTypeClass()),
                    create_schema_field("first_order_at", "TIMESTAMP", TimeTypeClass()),
                ],
            ),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_FCT_USER_ORDERS,
            aspect=create_ownership("alice@company.com", OwnershipTypeClass.TECHNICAL_OWNER),
        )
    )

    # Lineage with Fine-Grained Column-Level Lineage
    fine_grained_lineage = [
        FineGrainedLineageClass(
            upstreamType=FineGrainedLineageUpstreamTypeClass.FIELD_SET,
            upstreams=[f"urn:li:schemaField:({URN_USERS_RAW},email)"],
            downstreamType=FineGrainedLineageDownstreamTypeClass.FIELD,
            downstreams=[f"urn:li:schemaField:({URN_FCT_USER_ORDERS},user_email)"],
        ),
        FineGrainedLineageClass(
            upstreamType=FineGrainedLineageUpstreamTypeClass.FIELD_SET,
            upstreams=[f"urn:li:schemaField:({URN_ORDERS_RAW},order_amount)"],
            downstreamType=FineGrainedLineageDownstreamTypeClass.FIELD,
            downstreams=[f"urn:li:schemaField:({URN_FCT_USER_ORDERS},lifetime_value)"],
        ),
        FineGrainedLineageClass(
            upstreamType=FineGrainedLineageUpstreamTypeClass.FIELD_SET,
            upstreams=[f"urn:li:schemaField:({URN_ORDERS_RAW},order_id)"],
            downstreamType=FineGrainedLineageDownstreamTypeClass.FIELD,
            downstreams=[f"urn:li:schemaField:({URN_FCT_USER_ORDERS},total_orders)"],
        ),
    ]

    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_FCT_USER_ORDERS,
            aspect=UpstreamLineageClass(
                upstreams=[
                    UpstreamClass(dataset=URN_USERS_RAW, type=DatasetLineageTypeClass.TRANSFORMED),
                    UpstreamClass(dataset=URN_ORDERS_RAW, type=DatasetLineageTypeClass.TRANSFORMED),
                ],
                fineGrainedLineages=fine_grained_lineage,
            ),
        )
    )

    # 4. BI Chart & Dashboard with Ownership
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_CHART_REVENUE,
            aspect=ChartInfoClass(
                title="User Revenue Chart",
                description="Visualizes user lifetime value by cohort",
                lastModified=change_audit_stamps,
                inputs=[URN_FCT_USER_ORDERS],
            ),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_CHART_REVENUE,
            aspect=create_ownership("bob@company.com", OwnershipTypeClass.BUSINESS_OWNER),
        )
    )

    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_DASHBOARD_EXEC,
            aspect=DashboardInfoClass(
                title="Executive Revenue Dashboard",
                description="High level executive BI dashboard for revenue and churn",
                lastModified=change_audit_stamps,
                charts=[URN_CHART_REVENUE],
            ),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_DASHBOARD_EXEC,
            aspect=create_ownership("carol@company.com", OwnershipTypeClass.BUSINESS_OWNER),
        )
    )

    # 5. ML Layer: Individual ML Feature, Feature Table, and ML Model with Ownership
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ML_FEATURE_LTV,
            aspect=MLFeaturePropertiesClass(
                description="Calculated user lifetime value feature",
                dataType=MLFeatureDataTypeClass.CONTINUOUS,
                sources=[URN_FCT_USER_ORDERS],
            ),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ML_FEATURE_LTV,
            aspect=create_ownership("dave@company.com", OwnershipTypeClass.TECHNICAL_OWNER),
        )
    )

    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ML_FEATURES,
            aspect=MLFeatureTablePropertiesClass(
                description="SageMaker feature table for user churn model training",
                mlFeatures=[URN_ML_FEATURE_LTV],
            ),
        )
    )

    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ML_MODEL,
            aspect=MLModelPropertiesClass(
                description="Production XGBoost model predicting user churn risk",
                mlFeatures=[URN_ML_FEATURE_LTV],
            ),
        )
    )
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ML_MODEL,
            aspect=create_ownership("eve@company.com", OwnershipTypeClass.TECHNICAL_OWNER),
        )
    )

    # 6. Data Contract / Assertion on fct_user_orders
    mcps.append(
        MetadataChangeProposalWrapper(
            entityUrn=URN_ASSERTION_LTV,
            aspect=AssertionInfoClass(
                type=AssertionTypeClass.DATASET,
                datasetAssertion=DatasetAssertionInfoClass(
                    dataset=URN_FCT_USER_ORDERS,
                    scope=DatasetAssertionScopeClass.DATASET_COLUMN,
                    fields=[URN_FIELD_LTV],
                    operator=AssertionStdOperatorClass.NOT_NULL,
                ),
            ),
        )
    )

    # Emit all MCPs to DataHub
    # 6. Emit Tag Entity for BlastRadius Warning Tag
    tag_mcp = MetadataChangeProposalWrapper(
        entityType="tag",
        entityUrn="urn:li:tag:blastradius_pending_change",
        changeType=ChangeTypeClass.UPSERT,
        aspectName="tagProperties",
        aspect=TagPropertiesClass(
            name="blastradius_pending_change",
            description="Pending schema change warning added by BlastRadius agent"
        ),
    )
    mcps.append(tag_mcp)

    print(f"Emitting {len(mcps)} metadata change proposals to DataHub GMS at {config.datahub_gms_url}...")
    for mcp in mcps:
        emitter.emit(mcp)

    logger.info("Successfully seeded demo data stack with ownership into DataHub!")


def main() -> None:
    try:
        emitter = DataHubRestEmitter(gms_server=GMS_ENDPOINT)
        emit_metadata(emitter)
    except Exception as e:
        logger.error(f"Failed to emit metadata to DataHub: {e}")
        logger.info("Ensure DataHub is running locally via 'python -m datahub docker quickstart' before running this script.")
        sys.exit(1)


if __name__ == "__main__":
    main()
