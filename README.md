# Option Risk Explain

<p align="center">
  <img src="https://raw.githubusercontent.com/garroshub/OptionRiskExplain/main/assets/readme/hero-display.svg" width="100%" alt="Option Risk Explain: equity-options portfolio P&L attribution, with synthetic selloff results showing -$44,471 observed P&L, -$63,018 Delta and +$11,288 Vega">
</p>

**Explain an equity-option portfolio's daily P&L from opening Greeks, model revaluation and changes in market marks.** Inspect the factor contributions, reconcile the difference and identify contracts that need review.

<p align="center">
  <a href="https://garroshub.github.io/OptionRiskExplain/"><img src="https://raw.githubusercontent.com/garroshub/OptionRiskExplain/main/assets/readme/button-demo.svg" height="46" alt="Open interactive GitHub Pages demo"></a>
  <a href="#local-setup"><img src="https://raw.githubusercontent.com/garroshub/OptionRiskExplain/main/assets/readme/button-install.svg" height="46" alt="Installation instructions"></a>
  <a href="#pl-calculation"><img src="https://raw.githubusercontent.com/garroshub/OptionRiskExplain/main/assets/readme/button-method.svg" height="46" alt="P&L methodology and scope"></a>
  <a href="#example-portfolio"><img src="https://raw.githubusercontent.com/garroshub/OptionRiskExplain/main/assets/readme/button-cases.svg" height="46" alt="Example scenario results"></a>
</p>

Python 3.10+ · Python API / CLI / browser · Local CSV analysis · No Streamlit dependency

## See the desk move

The interactive report opens with a five-position SPY/AAPL book. Choose **Equity market selloff** to inspect a shock where SPY falls 5.5%, AAPL falls 6.0% and implied volatility rises by 5–6 percentage points.

```text
EQUITY MARKET SELLOFF                       05–06 OCT 2026
─────────────────────────────────────────────────────────
Observed portfolio P&L                           -$44,471
  Delta                                          -$63,018
  Vega                                           +$11,288
Positions                                              5
Exceptions                                             3
P&L reconciliation error                           $0.00
```

All inputs are synthetic. The attribution is calculated with the same `option_lab` engine used for custom portfolios. Greeks, full model repricing, market/model basis and individual contract flags are available in the report.

<p align="center">
  <a href="https://garroshub.github.io/OptionRiskExplain/"><img src="https://raw.githubusercontent.com/garroshub/OptionRiskExplain/main/assets/readme/risk-showcase.png" width="100%" alt="Interactive browser workbench with scenario selector, portfolio P&L, risk-factor contribution chart and exception review"></a>
</p>

## Example portfolio

| Scenario | Observed P&L | Exceptions |
| --- | ---: | ---: |
| Daily desk review | −$1,152 | 2 |
| Equity market selloff | −$44,471 | 3 |
| Volatility repricing | +$13,735 | 0 |
| Valuation exception | +$1,146 | 3 |

Switching the browser dropdown updates the report from a precomputed scenario record. No account, file upload or backend is required for these four examples.

**[Open the interactive GitHub Pages demo ↗](https://garroshub.github.io/OptionRiskExplain/)**

## Local setup

Install from the source repository:

```bash
git clone https://github.com/garroshub/OptionRiskExplain.git
cd OptionRiskExplain
python -m pip install -e .
python -m option_lab serve
```

Open **http://127.0.0.1:8765/**. The local server also accepts two CSV snapshots under **Custom portfolio analysis**, with JSON and CSV export.

The Python API can run without a browser:

```python
from pathlib import Path
from option_lab import explain_csv

report = explain_csv(
    Path("examples/positions_2026-10-05.csv").read_text(),
    Path("examples/positions_2026-10-06.csv").read_text(),
    exception_threshold=500,
)

print(report["totals"]["observed_pnl"])
print(report["totals"]["reconciliation_error"])
print(report["exceptions"])
```

CLI example with file exports:

```bash
python -m option_lab explain --start examples/positions_2026-10-05.csv --end examples/positions_2026-10-06.csv --threshold 500 --output report.json --csv-output contract-pnl.csv
```

The optional Yahoo Finance adapter is installed with `pip install -e ".[market]"`. Market data is available through `option-risk-explain quote SPY`, `option-risk-explain expirations SPY` and the local option-chain browser. Yahoo quotes are not used as a historical institutional mark feed.

## P&L calculation

<p align="center">
  <img src="https://raw.githubusercontent.com/garroshub/OptionRiskExplain/main/assets/readme/workflow.svg" width="100%" alt="Option P&L workflow: two input snapshots, opening Greek attribution and BSM repricing, then reconciled P&L and contract-level exceptions">
</p>

For an unchanged position, with signed contract quantity `Q`, multiplier `M` and end-of-day mark `P`:

```text
Observed P&L = Q × M × (P_end − P_start)

Greek explain:
  Delta0 × ΔSpot + 0.5 × Gamma0 × ΔSpot²
  + Vega0 × ΔIV + Theta0 × elapsed_days
  + Rho0 × ΔRate + isolated dividend-yield effect
  (all multiplied by Q × M)

Approximation residual = Full BSM repricing − Greek explain
Market/model basis     = Observed P&L − Full BSM repricing

Observed P&L = Greek explain + Approximation residual + Market/model basis
```

Vega and Rho use percentage-point changes; Theta uses calendar days. The two residuals are displayed separately. A market/model basis change can reflect differences in model assumptions, valuation marks or timestamps.

Exception checks cover approximation/basis amounts above a user-supplied USD threshold, crossed bid/ask quotes and marks outside the provided spread.

## Working with your own positions

Custom reports require two snapshots with identical contract identities, signed quantities and multipliers. Required CSV fields:

| Data | CSV fields |
| --- | --- |
| Contract | `underlying`, `option_type`, `expiry`, `strike` |
| Position | `quantity`, `multiplier` |
| Market inputs | `as_of`, `spot`, `mark`, `volatility`, `rate`, `dividend_yield` |
| Optional controls | `bid`, `ask`, `source` |

Dates use `YYYY-MM-DD`. Volatility, rates and dividend yields are annual decimal values (e.g. `0.25` for 25%). The [opening](examples/positions_2026-10-05.csv) and [closing](examples/positions_2026-10-06.csv) CSVs are included.

Generate the four browser cases with:

```bash
python -m scripts.make_risk_fixtures
python -m scripts.generate_scenarios
```

## Model scope and tests

The engine uses European Black–Scholes–Merton pricing, continuous dividends and ACT/365 maturity. It assumes unchanged USD-denominated positions. Trades, fees, funding, early exercise, settlement, FX and corporate actions are excluded. It is a research and workflow prototype, not a validated bank risk system or regulatory FRTB P&L Attribution Test.

```bash
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/pricing.test.mjs
python -m build --wheel --no-isolation
python tests/wheel_smoke.py
```

The tests cover prices and Greeks, signed-position P&L reconciliation, input validation, scenario consistency, HTTP endpoints, and Chrome desktop/mobile interactions. The installable distribution is `option-risk-explain`. The Python module remains `option_lab`, and the original `option-lab` CLI remains available.

---

**[Interactive demo](https://garroshub.github.io/OptionRiskExplain/)** · **[Source code](https://github.com/garroshub/OptionRiskExplain)** · **[Method](#pl-calculation)**
