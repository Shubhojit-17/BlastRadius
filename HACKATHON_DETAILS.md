# 🏆 DataHub Agent Hackathon — Project Reference & Submission Requirements

This file serves as the official reference for **The Agent Hackathon** hosted by DataHub on Devpost.

---

## 📅 Hackathon Overview

- **Host**: DataHub (Devpost)
- **Theme**: "Agents That Ship with Context" — Building AI agents leveraging DataHub's open-source context platform (MCP Server, Agent Context Kit, ML Lineage, DataHub Skills).
- **License Requirement**: Apache 2.0 open-source license file visible in the public GitHub repository root.

---

## 🎯 Target Hackathon Challenges Addressed by BlastRadius

BlastRadius combines **3 primary hackathon challenge categories**:

1. **Agents That Do Real Work**:
   - Reads DataHub through the MCP Server (`mcp-server-datahub@latest`) over stdio to trace column-level downstream impacts and data contract violations.
   - Takes real automated action and writes results back into the DataHub catalog (`add_tags`, `update_description` sentinel warnings, `add_structured_properties`) so humans and downstream agents inherit the risk context.
2. **Metadata-Aware Code Generation & Development**:
   - Analyzes PR git diffs touching SQL / dbt transformation models using SQLGlot AST parsing before code is merged.
   - Evaluates active schema assertions and data contracts from DataHub before generating an executive Markdown PR comment and posting CI risk verdicts.
3. **Production ML Agents**:
   - Traces end-to-end ML lineage from SQL dataset (`analytics.fct_user_orders`) -> SageMaker feature table (`user_churn_features`) -> SageMaker ML model (`churn_prediction_v2`).
   - Protects production ML models from silent upstream column drops and schema drift before deployment.

---

## ⚖️ Judging Criteria Alignment

| Judging Criterion | How BlastRadius Excels |
| :--- | :--- |
| **Use of DataHub** | Uses DataHub RestGraph API + stdio MCP Server (`get_entities`, `get_lineage_paths_between`, `add_tags`, `update_description`, `add_structured_properties`) for both catalog context reading and two-way write-back. |
| **Technical Execution** | Complete end-to-end Python engine with 0 shortcuts: SQLGlot AST resolver, graph analyzer, column-aware contract evaluator, MCP enrichment, transparent scoring, GitHub Action, and installable DataHub Skill. |
| **Originality** | Novel combination of column-level PR diff parsing with graph assertion checking and sentinel-guarded MCP catalog write-back. |
| **Real-World Usefulness** | Prevents breaking production dashboards and ML models during data engineering PR reviews — a daily high-stakes problem for data teams. |
| **Submission Quality** | Polished README, detailed architectural diagrams, automated verification scripts, sample output artifacts under `examples/`, and 3-minute video guide. |

---

## 📦 Required Hackathon Deliverables Checklist

- [x] Public GitHub Repository: `https://github.com/Shubhojit-17/BlastRadius`
- [x] Apache 2.0 License (`LICENSE` file in repo root)
- [x] Working Software Application (Runnable live against DataHub & offline zero-setup demo mode)
- [x] DataHub Agent Skill Packaging (`skills/blastradius-guardian/SKILL.md`)
- [x] Sample Output Artifacts (`examples/` directory containing JSON payloads and Markdown PR comments)
- [x] Comprehensive Documentation (`README.md` with setup guide, live runup instructions, and architecture)
- [ ] 3-Minute Demo Video (YouTube/Vimeo public link)
