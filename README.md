# BlastRadius 💥⚡

> **The DataHub Agent & GitHub Action that Guards Your Data Stack from Breaking Schema Changes.**

BlastRadius is an AI agent, GitHub Action, and installable DataHub Agent Skill that reviews Pull Requests touching data code (SQL, dbt models, schema migrations). It leverages DataHub's metadata context graph to compute the **column-aware downstream "blast radius"** of changes — identifying affected dashboards, ML features, production ML models, and registered owners, checking DataHub data contracts, posting auditable risk verdicts on PRs, and performing two-way metadata write-back to DataHub.

Built for **[The Agent Hackathon](https://datahub.devpost.com)** hosted by DataHub.

---

## 🏗️ Architecture & How It Works

```
┌────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Git PR Diff (SQL/dbt)  │ ───> │ SQLGlot AST Resolver    │ ───> │ DataHub Lineage Graph   │
└────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                              │
                                                                              ▼
┌────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ PR Comment & Verdict   │ <─── │ Transparent Risk Scoring│ <─── │ Data Contract Evaluator │
└────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
            │
            ▼ (Opt-In Write-Back via stdio mcp-server-datahub)
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ DataHub Catalog Write-Back: Tag Assets + Plain-Text Sentinel Warning + Structured Props   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **SQL AST Resolver**: Parses PR SQL files using SQLGlot to extract exact column-level modifications (`COLUMN_DROP`, `RENAME`, `TYPE_CHANGE`).
2. **Column-Level Lineage Graph**: Queries DataHub GMS to trace downstream dependencies specifically affected by changed columns (Looker charts/dashboards, SageMaker ML features, SageMaker ML models).
3. **Data Contract & Assertion Guard**: Evaluates whether PR column modifications violate active DataHub schema assertions or data contracts.
4. **DataHub MCP Agent Layer**: Connects over stdio to `mcp-server-datahub` to enrich risk narratives with live catalog documentation and explicit transformation paths.
5. **Auditable Point Rubric & Reporter**: Calculates transparent risk scores and generates formatted Markdown PR comments with required owner callouts.
6. **Two-Way Catalog Write-Back**: Annotates affected downstream assets with `blastradius_pending_change` tags, updates target dataset documentation using plain-text sentinel markers (`[BLASTRADIUS:START]`), and attaches structured property metadata.
7. **Reversible Graph Cleanup**: Provides a `cleanup_writeback` execution path to restore DataHub metadata byte-for-byte between PR evaluations.

---

## 🔌 DataHub Connection Ports Guide

- **Port 9002 (`http://localhost:9002`)**: **DataHub Frontend Web UI**
  - Use this in your browser to view datasets, column lineage graphs, active data contracts, tags, and catalog documentation.
- **Port 8080 (`http://localhost:8080`)**: **DataHub GMS (General Metadata Service) API**
  - Used programmatically by BlastRadius, the DataHub Python SDK, GraphQL API, and stdio MCP server (`mcp-server-datahub`) to query metadata and emit metadata proposals.

---

## ⚡ Zero-Setup Offline Demo (No Infrastructure Required)

You can run the complete BlastRadius pipeline end-to-end with **zero setup, zero Docker, zero DataHub Core, and zero API keys**:

```bash
python -m blastradius.demo
```

This demo uses `MockDataHubClient` and recorded fixtures under `examples/recorded/` to execute the full Resolver ➔ Analyzer ➔ Contracts ➔ MCP Agent ➔ Reporter pipeline and output the formatted PR comment with an exit code of `1` (HIGH RISK).

---

## 🚀 Live DataHub Execution & Hackathon Verification

To run the master live verification suite against your local DataHub instance (`http://localhost:8080`):

```bash
# 1. Seed demo graph into local DataHub Core
python demo/seed_data.py

# 2. Run master live E2E verification (Scenario A, Scenario B, Write-Back, Idempotency, Cleanup)
python scripts/verify_live_e2e_hackathon.py
```

### Why `--offline` is Used for `uvx`
When spawning `mcp-server-datahub` via `uvx`, the `--offline` flag instructs `uv` to launch the **locally cached, pre-installed Python package** on your machine rather than making PyPI network checks. The MCP server itself connects **100% LIVE** to your local DataHub instance (`http://localhost:8080`).

---

## 🤖 Packaging as a DataHub Agent Skill

BlastRadius is packaged as an installable DataHub Agent Skill under `skills/blastradius-guardian/`:

```
skills/blastradius-guardian/
├── SKILL.md                          # Core 5-step imperative workflow instructions
└── references/
    ├── risk_rubric.md                # Transparent point scoring rubric reference
    └── mcp_mutation_cheatsheet.md    # DataHub MCP mutation tool argument shapes
```

### Installation
You can add this skill to your agent environment using the Skills CLI:

```bash
npx skills add skills/blastradius-guardian
```

Compatible with Gemini CLI, Claude Code, Cursor, Copilot, Windsurf, and other Agent Skills runners.

---

## 📁 Repository Structure

- `blastradius/` - Core Python engine (Resolver, Analyzer, Contracts, MCP Agent, Reporter, Writeback, Orchestrator).
- `skills/blastradius-guardian/` - DataHub Agent Skill definition & reference guides.
- `demo/` - Reproducible DataHub graph seeding and teardown scripts.
- `.github/workflows/` - GitHub Action workflow definition (`blastradius.yml`).
- `examples/` - Sample PR comment outputs, assessment payloads, and SQL diff fixtures.
- `scripts/` - Automated test and verification scripts.

---

## 📄 License

This project is open source under the terms of the [Apache 2.0 License](LICENSE).
