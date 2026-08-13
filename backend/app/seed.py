"""Seed clients, SQLite rows, sample bank CSVs, tax history."""

from __future__ import annotations

import json
from pathlib import Path

from app import db
from app.paths import DATA, FIRM_CLIENTS, ensure_dirs


SAMPLE_CSV = """Date,Description,Amount
2025-05-01,AMAZON MKTPLACE PA,-54.33
2025-05-02,STRIPE PAYMENTS FEE,-29.00
2025-05-03,SQUARE DEPOSIT,640.00
2025-05-04,UNKNOWN MERCHANT XYZ,-17.50
2025-05-05,SHELL OIL 7741,-58.20
2025-05-06,STARBUCKS STORE 123,-12.45
2025-05-07,FACEBOOK ADS,-200.00
"""


def seed() -> dict:
    ensure_dirs()
    db.init_db()

    harbor_path = str(FIRM_CLIENTS / "harbor_lemon.beancount")
    north_path = str(FIRM_CLIENTS / "northside_rentals.beancount")

    db.upsert_client("harbor_lemon", "Harbor Lemon Co.", "sole_prop", harbor_path, 85)
    db.upsert_client("northside_rentals", "Northside Rentals", "s_corp", north_path, 85)

    # Prior year tax payloads
    db.save_prior_year(
        "harbor_lemon",
        2023,
        {
            "tax_year": 2023,
            "entity": "Schedule C",
            "entity_type": "sole_prop",
            "prep_year": 2025,
            "forms": [{"type": "W2"}, {"type": "1099NEC"}, {"type": "PRIOR_RETURN"}],
            "schedules": ["Schedule C", "Schedule SE"],
            "net_income": "82000",
            "tax_liability": "18500",
        },
    )
    db.save_prior_year(
        "harbor_lemon",
        2024,
        {
            "tax_year": 2024,
            "entity": "Schedule C",
            "entity_type": "sole_prop",
            "prep_year": 2025,
            "forms": [{"type": "W2"}, {"type": "1099NEC"}, {"type": "1099INT"}],
            "schedules": ["Schedule C"],
            "net_income": "91000",
            "tax_liability": "20100",
        },
    )
    db.save_prior_year(
        "northside_rentals",
        2023,
        {
            "tax_year": 2023,
            "entity": "S-Corp",
            "entity_type": "s_corp",
            "prep_year": 2025,
            "forms": [{"type": "W2"}, {"type": "K1"}, {"type": "PRIOR_RETURN"}],
            "schedules": ["Form 1120-S"],
            "net_income": "145000",
            "tax_liability": "24000",
        },
    )
    db.save_prior_year(
        "northside_rentals",
        2024,
        {
            "tax_year": 2024,
            "entity": "S-Corp",
            "entity_type": "s_corp",
            "prep_year": 2025,
            "forms": [{"type": "W2"}, {"type": "K1"}],
            "schedules": ["Form 1120-S"],
            "net_income": "162000",
            "tax_liability": "25500",
        },
    )

    # Clear and reseed tax savings history for YoY charts
    with db.connect() as conn:
        conn.execute("DELETE FROM tax_savings_history")
        conn.execute("DELETE FROM document_checklist")

    for year, rows in {
        2023: [
            ("harbor_lemon", "QBI Deduction (20%)", "3200", "18500", "15300"),
            ("harbor_lemon", "Section 179", "1800", "18500", "15300"),
            ("northside_rentals", "S-Corp Salary Optimization", "9200", "33200", "24000"),
            ("northside_rentals", "Augusta Rule", "1400", "33200", "24000"),
        ],
        2024: [
            ("harbor_lemon", "QBI Deduction (20%)", "3600", "20100", "16200"),
            ("harbor_lemon", "Augusta Rule", "1200", "20100", "16200"),
            ("northside_rentals", "S-Corp Salary Optimization", "10100", "35600", "25500"),
            ("northside_rentals", "QBI Deduction (20%)", "4100", "35600", "25500"),
            ("northside_rentals", "Section 179", "2400", "35600", "25500"),
        ],
    }.items():
        for client_id, strategy, savings, cur, opt in rows:
            db.add_tax_savings(client_id, year, strategy, savings, cur, opt)

    # Checklist for 2025 prep
    from app.tax import ingest_prior_year

    for client_id in ("harbor_lemon", "northside_rentals"):
        prior = db.get_prior_year(client_id, 2024)
        if prior:
            ingest_prior_year(client_id, prior["payload"])

    # Sample bank CSV for Harbor
    sample_path = DATA / "samples" / "harbor_bank_may2025.csv"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(SAMPLE_CSV)

    return {
        "clients": db.list_clients(),
        "sample_csv": str(sample_path),
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    print(json.dumps(seed(), indent=2))
