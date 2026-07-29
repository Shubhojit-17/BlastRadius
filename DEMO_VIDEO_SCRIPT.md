# 🎬 BlastRadius — 3-Minute Hackathon Demo Video Script & Guide

This guide contains the exact script, terminal commands, screen actions, and graph reset instructions for recording your 3-minute Devpost hackathon demo video.

---

## 🛠️ Commands Cheatsheet for Recording

### 1. Reset DataHub to Clean State (Before Video & Between Takes)
To wipe any leftover warning tags or descriptions and restore the clean graph:

```cmd
python demo/seed_data.py
```

### 2. Zero-Setup Offline Demo Command
Runs the full pipeline using offline recorded fixtures (works with 0 infrastructure):

```cmd
python -m blastradius.demo
```

### 3. Live PR Assessment + Two-Way Write-Back Command
Executes live against DataHub GMS (`http://localhost:8080`), evaluates column drop on `lifetime_value`, and writes findings back into DataHub:

```cmd
python -c "from blastradius.orchestrator import run_pipeline; run_pipeline('SELECT user_id, first_order_at, lifetime_value FROM analytics.fct_user_orders;', 'SELECT user_id, first_order_at FROM analytics.fct_user_orders;', use_mock=False, write_back=True, pr_number=101)"
```

### 4. Live Reversible Graph Cleanup Command
Strips the warning block and detaches tags from DataHub GMS:

```cmd
python -c "from blastradius.orchestrator import run_pipeline; from blastradius.writeback import cleanup_writeback; report, _ = run_pipeline('SELECT user_id, first_order_at, lifetime_value FROM analytics.fct_user_orders;', 'SELECT user_id, first_order_at FROM analytics.fct_user_orders;', use_mock=False); cleanup_writeback(report, use_mock=False)"
```

---

## 📽️ Video Script & Step-by-Step Shot List (Target: < 3 Minutes)

### Scene 1: The Problem & Introduction (0:00 – 0:35)
- **Screen Action**: Display the `fct_user_orders` model or git PR diff.
- **Voiceover**:
  > *"Data teams push dbt and SQL code changes every day. But when a developer drops or renames a column in a pull request, how do you know if it will silently break an executive Looker dashboard or bring down a production SageMaker ML model? Standard CI checks only test if SQL compiles — they are completely blind to catalog context.*
  > *Meet **BlastRadius** — an AI agent, GitHub Action, and DataHub Agent Skill that reviews SQL PRs for column-level downstream impact, checks DataHub data contracts, scores PR risk, and writes context back into DataHub."*

---

### Scene 2: Live DataHub Context & Lineage (0:35 – 1:10)
- **Screen Action**: Switch browser to **`http://localhost:9002`**.
  - Navigate to dataset `analytics.fct_user_orders`.
  - Click on **Lineage** tab, toggle **Column-Level Lineage ON**, and click on column **`lifetime_value`**.
  - Show the path tracing to Looker chart `user_revenue_chart`, Looker dashboard `exec_revenue_dashboard`, SageMaker feature `user_ltv_feature`, and SageMaker ML model `churn_prediction_v2`.
  - Click on **Quality ➔ Assertions** tab (or **Data Contract** tab) to show the active contract assertion protecting column `lifetime_value` (`Column lifetime_value values are not null`).
- **Voiceover**:
  > *"Here in DataHub Core, we have a dataset called `fct_user_orders`. Using DataHub's column-level lineage, we see that `lifetime_value` feeds a Looker revenue dashboard AND a production XGBoost churn prediction model. Furthermore, DataHub has an active data contract assertion protecting this schema."*

---

### Scene 3: BlastRadius PR Evaluation & Auditable Scoring (1:10 – 1:55)
- **Screen Action**: Switch to Terminal and run:
  ```cmd
  python -c "from blastradius.orchestrator import run_pipeline; run_pipeline('SELECT user_id, first_order_at, lifetime_value FROM analytics.fct_user_orders;', 'SELECT user_id, first_order_at FROM analytics.fct_user_orders;', use_mock=False, write_back=True, pr_number=101)"
  ```
  Highlight the terminal output showing:
  - SQLGlot AST detecting `COLUMN_DROP` on `lifetime_value`
  - Contract assertion `fct_user_orders_ltv_schema` status: `VIOLATED`
  - Score: `100.0/100.0` (`HIGH RISK`) with hard override rationale.
  - Formatted PR comment markdown with 4 affected owners listed.
- **Voiceover**:
  > *"Now a developer opens a PR dropping `lifetime_value`. BlastRadius parses the AST diff using SQLGlot, traces column lineage in DataHub, and checks active contracts. It flags the broken data contract, computes an auditable point score of 100/100, assigns a HIGH RISK verdict, and lists the 4 cross-team owners required to approve the PR."*

---

### Scene 4: Live DataHub Catalog Write-Back (1:55 – 2:35)
- **Screen Action**: Switch browser back to **`http://localhost:9002`** and refresh.
  - Show the **Description** box on `fct_user_orders` containing `[BLASTRADIUS:START]` warning block.
  - Show yellow/red tag **`blastradius_pending_change`** attached to `fct_user_orders`.
  - Navigate to **Manage Tags** (`http://localhost:9002/tags`) showing `blastradius_pending_change` applied to **5 entities** (1 Dataset, 1 Dashboard, 1 Chart, 1 Feature, 1 Model).
- **Voiceover**:
  > *"Here is the key differentiator: BlastRadius doesn't just read DataHub — it writes findings back via DataHub's MCP mutation tools! Anyone browsing DataHub now sees a prominent warning marker on `fct_user_orders` detailing the PR risk, and the yellow `blastradius_pending_change` warning tag is attached across all 5 affected downstream entities in the graph!"*

---

### Scene 5: Reversible Cleanup, DataHub Agent Skill & Wrap-up (2:35 – 3:00)
- **Screen Action**:
  - Run cleanup in terminal to show exact graph restoration.
  - Briefly show `skills/blastradius-guardian/SKILL.md` in IDE.
- **Voiceover**:
  > *"When the PR is closed or merged, BlastRadius executes reversible cleanup, restoring original catalog documentation byte-for-byte. BlastRadius is also packaged as an installable DataHub Agent Skill compatible with Gemini CLI, Claude Code, and Cursor.
  > BlastRadius protects your data stack by giving AI agents full context to act. Thank you!"*
