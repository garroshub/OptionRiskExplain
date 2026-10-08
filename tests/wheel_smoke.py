"""Clean temporary-wheel installation smoke test (no network, no global pip mutation)."""
from pathlib import Path
from subprocess import run
import sys
from tempfile import TemporaryDirectory
import venv

ROOT = Path(__file__).resolve().parents[1]
wheel = next((ROOT / "dist").glob("garros_option_lab-0.2.0-*.whl"))
with TemporaryDirectory(prefix="optionlab-wheel-") as folder:
    temp = Path(folder)
    environment = temp / "venv"
    venv.create(environment, with_pip=True)
    executable = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    run([str(executable), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
        check=True, capture_output=True, text=True, cwd=temp)
    program = """
from option_lab import price_european, explain_csv
from option_lab.server import DOCS
assert abs(price_european(100, 100, 1, .05, 0, .2)['call'] - 10.45058357) < 1e-5
assert (DOCS / 'index.html').is_file(), DOCS
assert (DOCS / 'market.js').is_file(), DOCS
assert (DOCS / 'risk.js').is_file(), DOCS
assert (DOCS / 'risk.css').is_file(), DOCS
assert (DOCS / 'risk-first.css').is_file(), DOCS
assert (DOCS / 'risk-scenarios.json').is_file(), DOCS
assert (DOCS / 'risk-demo.json').is_file(), DOCS
assert (DOCS / 'positions_2026-10-05.csv').is_file(), DOCS
report=explain_csv((DOCS / 'positions_2026-10-05.csv').read_text(),
                   (DOCS / 'positions_2026-10-06.csv').read_text())
assert report['position_count']==5
assert abs(report['totals']['reconciliation_error'])<1e-8
assert (DOCS / 'assets/favicon.svg').is_file(), DOCS
print('INSTALLED_WHEEL_ALL_FEATURES_OK', DOCS)
"""
    result = run([str(executable), "-c", program], cwd=temp, check=True,
                 capture_output=True, text=True, encoding="utf-8")
    print(result.stdout.strip())
