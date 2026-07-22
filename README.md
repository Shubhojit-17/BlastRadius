# BlastRadius 💥⚡

An AI agent + GitHub Action that reviews Pull Requests touching data code (SQL, dbt models, schema migrations). It leverages DataHub's metadata graph to compute the downstream "blast radius" of changes — identifying affected dashboards, ML features, models, and owners, checking DataHub data contracts and assertions, posting risk verdicts on PRs, and writing assessment metadata back to DataHub.

## Features

- **SQL & dbt Parser**: Parses PR git diffs using SQLGlot to extract modified tables, views, and columns.
- **DataHub Lineage Graph Integration**: Fetches downstream impacts up to specified graph depths.
- **Data Assertion & Contract Guard**: Evaluates whether PR diffs break active DataHub data contracts or schema assertions.
- **Automated PR Reporter**: Generates executive summaries, risk scores, and Markdown PR comments with actionable owner warnings.
- **DataHub Feedback Writeback**: Pushes assessment results and risk metadata back into DataHub via the `acryl-datahub` SDK.

## Repository Layout

- `blastradius/` - Core Python package modules (Resolver, Analyzer, Contracts, Reporter, Writeback, Orchestrator).
- `.github/workflows/` - GitHub Action integration workflows.
- `examples/` - Sample PR comment outputs and JSON assessment payloads.

## License

This project is open source under the terms of the [Apache 2.0 License](LICENSE).
