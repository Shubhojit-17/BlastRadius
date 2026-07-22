## 💥 BlastRadius PR Assessment: HIGH RISK (Risk Score: 78.5 / 100)

> [!WARNING]
> This PR modifies core upstream models impacting **12 downstream assets**, including **2 production dashboards** and **1 ML feature set**.

---

### 🔍 Direct PR Changes
- `analytics.fct_orders`: Dropped column `customer_lifetime_value` (`COLUMN_DROP`)
- `analytics.dim_users`: Modified data type `user_id` from `INT` to `VARCHAR` (`COLUMN_TYPE_CHANGE`)

---

### 🌊 Downstream Impact Breakdown

| Asset URN | Asset Name | Type | Lineage Depth | Owners |
|---|---|---|---|---|
| `urn:li:dataset:(...,analytics.monthly_revenue_summary,PROD)` | `monthly_revenue_summary` | `dataset` | 1 hop | `@data-team` |
| `urn:li:dashboard:(looker,dashboards.exec_kpis)` | `Executive KPI Dashboard` | `dashboard` | 2 hops | `@finance-bi` |
| `urn:li:mlFeatureTable:(...,user_churn_features)` | `User Churn Features` | `mlFeature` | 3 hops | `@ml-eng` |

---

### ⚠️ Contract & Assertion Violations

- ❌ `urn:li:assertion:schema_contract_fct_orders`: **FAILED** — Field `customer_lifetime_value` is required by data contract.
- ⚠️ `urn:li:assertion:freshness_dim_users`: **POTENTIALLY_BROKEN** — Upstream join key modified.

---

### 🏷️ DataHub Status
*Assessment results & risk tag `blastradius:high-risk` written back to DataHub metadata graph.*
