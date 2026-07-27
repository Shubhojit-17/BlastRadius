# BlastRadius 💥⚡

An AI agent + GitHub Action that reviews Pull Requests touching data code (SQL, dbt models, schema migrations). It leverages DataHub's metadata graph to compute the column-aware downstream "blast radius" of changes — identifying affected dashboards, ML features, models, and owners, checking DataHub data contracts and assertions, posting risk verdicts on PRs, and writing assessment metadata back to DataHub.

---

## ⚡ Zero-Setup Offline Demo (Zero Infrastructure Required)

You can run the full BlastRadius pipeline end-to-end with **zero setup, zero Docker, zero DataHub Core, and zero API keys**:

```bash
python -m blastradius.demo
```

This demo uses `MockDataHubClient` and offline recorded fixtures under `examples/recorded/` to execute the complete Resolver ➔ Analyzer ➔ Contracts ➔ MCP Agent ➔ Reporter pipeline and output the formatted PR comment with an exit code of `1` (HIGH RISK).

---

## 🚀 Live DataHub & GitHub Action Deployment Note

- **GitHub Action Workflow**: Defined in `.github/workflows/blastradius.yml`.
- **Runner Requirement**: Standard GitHub-hosted cloud runners (`runs-on: ubuntu-latest`) cannot connect to a DataHub instance hosted locally on `http://localhost:8080`.
- **Deployment Options**:
  - For local live PR evaluation, use a **self-hosted GitHub Action runner** running on your local machine alongside DataHub Core.
  - Or configure `DATAHUB_GMS_URL` secret to point to a publicly reachable DataHub GMS endpoint or ngrok tunnel URL.

---

## Features

- **SQL & dbt Parser**: Parses PR SQL files using SQLGlot to extract modified tables, views, and columns.
- **Column-Aware Lineage Graph**: Fetches downstream impacts (charts, dashboards, ML features, ML models) specifically affected by changed columns.
- **Data Contract & Assertion Guard**: Evaluates whether PR column changes violate active DataHub data contracts or schema assertions.
- **MCP-Powered Agent Layer**: Connects via stdio to `mcp-server-datahub` to enrich risk narratives with live catalog documentation and transformation paths.
- **Automated PR Reporter**: Generates auditable risk scores, explicit point breakdowns, and Markdown PR comments with owner action callouts.

---

## License

This project is open source under the terms of the [Apache 2.0 License](LICENSE).
