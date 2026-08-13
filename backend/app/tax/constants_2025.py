"""Tax constants for TY2025 — planning estimates, not tax advice."""

from decimal import Decimal

# All figures are illustrative planning constants for the prototype.
TAX_YEAR = 2025
DISCLAIMER = "Estimates for planning purposes only — not tax advice."

MEALS_DEDUCTIBLE_PCT = Decimal("0.50")

# Self-employment tax (illustrative)
SE_TAX_RATE = Decimal("0.153")  # 15.3% combined
SE_INCOME_FACTOR = Decimal("0.9235")

# Ordinary + SE proxy for sole prop comparison
ORDINARY_RATE = Decimal("0.24")  # illustrative marginal
CORP_PAYROLL_TAX_EMPLOYEE = Decimal("0.0765")
CORP_PAYROLL_TAX_EMPLOYER = Decimal("0.0765")

# QBI (IRC 199A) — simplified
QBI_RATE = Decimal("0.20")
QBI_THRESHOLD_SINGLE = Decimal("191950")
QBI_THRESHOLD_MFJ = Decimal("383900")

# Section 179 — illustrative cap
SECTION_179_CAP = Decimal("1220000")

# Augusta Rule — 14 day rental to corp (illustrative daily rate calc elsewhere)
AUGUSTA_MAX_DAYS = 14

# Standard mileage (illustrative)
STANDARD_MILEAGE_RATE = Decimal("0.70")
