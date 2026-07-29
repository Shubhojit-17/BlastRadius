# BlastRadius Risk Scoring Rubric

BlastRadius uses a transparent, auditable point rubric to calculate PR risk scores and assign risk verdicts.

---

## 📊 Point Weights

- **Violated Data Contract**: `+50.0 pts` per broken contract assertion
- **Downstream Production ML Model**: `+25.0 pts` if a production ML model is in the downstream lineage
- **Downstream Affected Assets**: `+5.0 pts` per affected downstream asset (chart, dashboard, feature, model)
- **Multi-Hop Lineage Depth**: `+5.0 pts` per hop depth > 1
- **Cross-Team Owners Affected**: `+5.0 pts` per additional distinct owner > 1

---

## 🚨 Risk Thresholds & Rules

- **Capped Score**: Raw score capped at `100.0 / 100.0`
- **Hard Override**: Any `VIOLATED` contract forces `HIGH RISK` (and non-zero exit code `1`)
- **HIGH RISK**: Score >= `50.0` OR broken contract (Exit Code `1`, CI Failed)
- **MEDIUM RISK**: Score >= `30.0` and < `50.0` (Exit Code `0`, CI Passed with Warning)
- **LOW RISK**: Score < `30.0` (Exit Code `0`, CI Passed)
