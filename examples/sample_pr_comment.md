# 🛡️ BlastRadius PR Assessment: HIGH RISK

> ⚠️ **CI CHECK FAILED**: High-risk schema/contract changes detected. Review from affected owners required.

---

### 🚨 Broken Data Contracts & Assertions
> 💥 **CONTRACT VIOLATION:** This PR violates data contract `fct_user_orders_ltv_schema`!
> **Reason:** Data contract assertion VIOLATED: Required column 'lifetime_value' is column_drop by PR (Dropped column 'lifetime_value' from fct_user_orders).

---

### 📊 Deterministic Impact Summary
- **Target Model:** `fct_user_orders`
- **Change Type:** `COLUMN_DROP` on column(s) `lifetime_value`
- **Risk Verdict:** **HIGH RISK** (Score: `100.0/100.0`)
- **Primary Rationale:** HIGH RISK (Hard Override: 1 violated data contract(s))

#### Auditable Score Arithmetic Breakdown
- `+50.0 pts` -- 1 Violated Data Contract(s) (fct_user_orders_ltv_schema)
- `+25.0 pts` -- Production ML Model in downstream lineage
- `+20.0 pts` -- 4 Downstream Affected Asset(s) (5.0 pts / asset)
- `+5.0 pts` -- Multi-Hop Lineage Depth 2
- `+15.0 pts` -- 4 Cross-Team Owners Affected

#### Downstream Affected Assets (4 Total, Max Hop Depth: 2)
| Asset Type | Asset Name | Hop Depth | Registered Owners |
| :--- | :--- | :---: | :--- |
| 📊 `CHART` | `user_revenue_chart` | 1 | `@bob@company.com` |
| 📈 `DASHBOARD` | `exec_revenue_dashboard` | 2 | `@carol@company.com` |
| 🧪 `MLFEATURE` | `user_ltv_feature` | 1 | `@dave@company.com` |
| 🤖 `MLMODEL` | `churn_prediction_v2` | 2 | `@eve@company.com` |

#### 👥 Action Required from Owners
The following **4 owners** must review and approve this PR:
- **@bob@company.com** (owns impacted downstream assets)
- **@carol@company.com** (owns impacted downstream assets)
- **@dave@company.com** (owns impacted downstream assets)
- **@eve@company.com** (owns impacted downstream assets)

---

### 🔍 DataHub MCP-Enriched Catalog Context
*(Retrieved via DataHub MCP stdio tools: get_entities, get_lineage_paths_between)*

- **Catalog Descriptions (`get_entities`):**
  - **`analytics.fct_user_orders`**: *"Derived dbt model for user lifetime value and order metrics"*
  - **`exec_revenue_dashboard`**: *"High level executive BI dashboard for revenue and churn"*
  - **`user_revenue_chart`**: *"Visualizes user lifetime value by cohort"*
  - **`churn_prediction_v2`**: *"Production XGBoost model predicting user churn risk"*
- **Explicit Lineage Path (`get_lineage_paths_between`):**
  - `snowflake,analytics.fct_user_orders,PROD [DATASET] -> sagemaker,user_ltv_feature [MLFEATURE] -> sagemaker,churn_prediction_v2,PROD [MLMODEL]`
