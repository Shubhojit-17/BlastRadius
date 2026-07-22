# Phase 1: Local DataHub & Breakable Demo Data Stack 💥

This directory contains the reproducible setup scripts and documentation to stand up a local open-source DataHub instance and seed it with a realistic, breakable data stack featuring column-level lineage and assertions.

---

## 1. Quickstart: Launch Local DataHub Instance

Ensure Docker Desktop is running, then launch DataHub using the official CLI tool:

```bash
# 1. Install acryl-datahub CLI tool (if not already installed)
pip install -r requirements.txt

# 2. Start DataHub Docker containers
datahub docker quickstart
```

### Health Verification & Endpoints
- **DataHub Web UI**: [http://localhost:9002](http://localhost:9002) (Default Credentials: `datahub` / `datahub`)
- **GMS Backend Server**: `http://localhost:8080` (API & SDK Emitter Endpoint)

Verify health by checking container status (`docker ps`) or visiting `http://localhost:9002` in your browser.

---

## 2. Seed the Demo Data Stack

Once DataHub is healthy, run the seed script to publish the demo metadata graph:

```bash
python demo/seed_data.py
```

### Ingested Demo Graph Overview

```
raw_postgres.public.orders (order_amount)
  └──> snowflake.analytics.fct_user_orders (lifetime_value) [Has Data Contract / Schema Assertion]
         ├──> Looker Chart: user_revenue_chart ──> Looker Dashboard: exec_revenue_dashboard
         └──> ML Feature: user_churn_features (user_ltv_feature) ──> ML Model: churn_prediction_v2
```

---

## 3. UI Verification Steps

1. Open **[http://localhost:9002](http://localhost:9002)** in your browser and log in with `datahub` / `datahub`.
2. **Search for `fct_user_orders`**:
   - Navigate to the **Lineage** tab.
   - Toggle **Column-Level Lineage** ON.
   - Click on the `lifetime_value` column to observe the trace upstream to `raw_postgres.public.orders.order_amount` and downstream to the BI chart and ML feature set.
3. **Verify Data Assertion / Contract**:
   - Navigate to the **Validation / Assertions** tab on `fct_user_orders`.
   - Verify that the schema assertion requiring `lifetime_value` is active.

---

## 4. Teardown Instructions

To reset or remove the seeded environment:

```bash
# Option A: Soft reset - remove seeded metadata from DataHub
datahub nuke

# Option B: Complete teardown - stop and remove Docker containers
datahub docker nuke
```
