"""Generate the static synthetic risk report used by GitHub Pages and local UI."""
import json
from pathlib import Path
from option_lab.risk import explain_csv

REPO=Path(__file__).resolve().parents[1]
result=explain_csv(
    (REPO/"examples"/"positions_2026-10-05.csv").read_text(encoding="utf-8"),
    (REPO/"examples"/"positions_2026-10-06.csv").read_text(encoding="utf-8"),
    exception_threshold=500.0
)
(REPO/"docs"/"risk-demo.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
for day in ("2026-10-05","2026-10-06"):
    (REPO/"docs"/f"positions_{day}.csv").write_text(
      (REPO/"examples"/f"positions_{day}.csv").read_text(encoding="utf-8"),encoding="utf-8")
print("SYNTHETIC_RISK_DEMO",result["position_count"],"contracts",
      "observed_pnl",round(result["totals"]["observed_pnl"],2),
      "exceptions",result["exception_count"],
      "reconcile",result["totals"]["reconciliation_error"])
