# 🎬 BlastRadius — Master 3-Minute Hackathon Demo Video Script

This is your single, chronological video recording script. All terminal commands are embedded inline directly in each scene where they are executed, with voiceover text aligned to explain what command is being typed and what action it takes.

---

## ⚙️ Pre-Recording Setup: Graph Reset

Before recording your video (or between recording takes), run this command to wipe any leftover warning tags or descriptions and reset DataHub to a clean baseline:

```cmd
python demo/seed_data.py
```

---

## 📽️ Chronological Video Script (Target Duration: 3:00)

### Scene 1: The Problem & Introduction (0:00 – 0:30)
- **Screen Action**: Display your IDE showing the `fct_user_orders` SQL query or a git PR diff.
- **Voiceover**:
  > *"Data engineering teams push dbt and SQL changes every day. But when a developer drops or renames a column in a pull request, how do you know if it will silently break an executive Looker dashboard or crash a production SageMaker ML model? Standard CI checks only verify SQL syntax — they are completely blind to catalog context.*
  > *Meet **BlastRadius** — an AI agent, GitHub Action, and DataHub Agent Skill that evaluates SQL PRs for column-level downstream impact, checks DataHub data contracts, calculates auditable risk scores, and writes findings directly back into DataHub."*

---

### Scene 2: Live DataHub Context & Column Lineage (0:30 – 1:05)
- **Screen Action**: Switch browser to **`http://localhost:9002`**.
  1. Search for and open dataset **`analytics.fct_user_orders`**.
  2. Click on the **Lineage** tab, expand **`Columns (5) ˅`**, and click on column **`lifetime_value`**.
  3. Show the highlighted purple lineage path tracing downstream to Looker chart `user_revenue_chart`, dashboard `exec_revenue_dashboard`, SageMaker feature `user_ltv_feature`, and SageMaker ML model `churn_prediction_v2`.
  4. Click on **Quality ➔ Assertions** tab to show the active contract assertion protecting `lifetime_value` (`Column lifetime_value values are not null`).
- **Voiceover**:
  > *"Here in DataHub Core at port 9002, we have a dataset called `fct_user_orders`. Expanding DataHub's column-level lineage on `lifetime_value`, we see it directly feeds a Looker revenue dashboard AND a production XGBoost churn prediction model. Under the Quality tab, DataHub has an active schema contract assertion protecting this column."*

---

### Scene 3: Live PR Evaluation & MCP Write-Back (1:05 – 1:55)
- **Screen Action**: Switch to Terminal and run this live evaluation command:

  ```cmd
  set PYTHONIOENCODING=utf-8 && python -c "from blastradius.orchestrator import run_pipeline; report, _ = run_pipeline('SELECT user_id, first_order_at, lifetime_value FROM analytics.fct_user_orders;', 'SELECT user_id, first_order_at FROM analytics.fct_user_orders;', use_mock=False, write_back=True, pr_number=101); print(report.summary_markdown)"
  ```

- **Screen Highlight**: Point to terminal output:
  - SQLGlot AST detecting `COLUMN_DROP` on `lifetime_value`
  - Data contract assertion status: `VIOLATED`
  - Auditable Score: `100.0/100.0` (`HIGH RISK verdict`)
  - Formatted PR comment markdown with 4 cross-team owners required to approve
- **Voiceover**:
  > *"Now a developer opens Pull Request #101 removing `lifetime_value` from `fct_user_orders`. We run BlastRadius live against DataHub GMS. BlastRadius parses the SQL AST diff using SQLGlot, traces column lineage in DataHub, and evaluates active contract assertions. It catches the broken data contract, calculates an auditable score of 100 out of 100, assigns a HIGH RISK verdict, identifies the 4 cross-team owners required for review, and triggers two-way catalog write-back via DataHub MCP tools."*

---

### Scene 4: Inspecting Live Catalog Write-Back in DataHub UI (1:55 – 2:30)
- **Screen Action**: Switch browser back to **`http://localhost:9002`** and refresh `analytics.fct_user_orders`.
  1. Show the **Documentation / Description** box containing the `[BLASTRADIUS:START]` schema impact warning block.
  2. Show the **`blastradius_pending_change`** tag attached to `fct_user_orders`.
  3. Navigate to **Manage Tags** (`http://localhost:9002/tags`) and click on `blastradius_pending_change` to show it automatically tagged **5 downstream entities** across datasets, dashboards, charts, ML features, and ML models.
- **Voiceover**:
  > *"Here is the key differentiator: BlastRadius doesn't just read DataHub — it acts on it! Refreshing DataHub UI, anyone browsing the catalog immediately sees a prominent warning block in `fct_user_orders` detailing the PR risk level and broken contract. Looking at Manage Tags, BlastRadius used DataHub's MCP mutation tools to tag all 5 affected downstream entities with `blastradius_pending_change` so catalog users are warned before the PR merges."*

---

### Scene 5: Reversible Graph Cleanup & DataHub Agent Skill Packaging (2:30 – 3:00)
- **Screen Action**:
  1. Switch to Terminal and run the reversible cleanup command:
     ```cmd
     python -c "from blastradius.orchestrator import run_pipeline; from blastradius.writeback import cleanup_writeback; report, _ = run_pipeline('SELECT user_id, first_order_at, lifetime_value FROM analytics.fct_user_orders;', 'SELECT user_id, first_order_at FROM analytics.fct_user_orders;', use_mock=False); cleanup_writeback(report, use_mock=False)"
     ```
  2. Switch IDE to display [`skills/blastradius-guardian/SKILL.md`](file:///e:/BlastRadius/skills/blastradius-guardian/SKILL.md).
- **Voiceover**:
  > *"When the PR is closed or merged, running BlastRadius cleanup strips the warning block and detaches the tags, restoring original catalog documentation byte-for-byte. BlastRadius is also packaged as an installable DataHub Agent Skill compatible with Gemini CLI, Claude Code, and Cursor.
  > BlastRadius protects your data stack by giving AI agents full context to act. Thank you!"*
