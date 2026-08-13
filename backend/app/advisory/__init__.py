"""Advisory: reasonable comp + tax savings visualizations data."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from app import db
from app.money import money
from app.paths import DICTIONARIES
from app.tax import constants_2025 as C


def load_industry_wages() -> list[dict[str, Any]]:
    path = DICTIONARIES / "industry_wages.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def reasonable_comp(
    net_income: Decimal | str,
    hours_worked: Decimal | str | float | int,
    industry_code: str,
    entity_type: str,
) -> dict[str, Any]:
    if entity_type != "s_corp":
        return {
            "enabled": False,
            "message": "Reasonable compensation analysis applies to S-Corp owners only.",
            "disclaimer": C.DISCLAIMER,
        }

    net = money(net_income)
    hours = Decimal(str(hours_worked))
    fte = min(Decimal("1"), hours / Decimal("2080"))
    industries = load_industry_wages()
    industry = next((i for i in industries if i["code"] == industry_code), None)
    if not industry:
        industry = industries[0] if industries else {"code": "GEN", "title": "General", "median_wage": "75000"}

    median = money(industry["median_wage"])
    comparable = money(median * fte)
    # clamp: salary should not exceed net income, and typically leave some profit for distributions
    recommended = money(min(comparable, net * money("0.60") if net > 0 else money(0)))
    low = money(recommended * money("0.85"))
    high = money(min(recommended * money("1.15"), net * money("0.80") if net > 0 else recommended))

    return {
        "enabled": True,
        "industry": industry,
        "hours_worked": str(hours),
        "fte": str(fte.quantize(Decimal("0.01"))),
        "comparable_wage": str(comparable),
        "recommended_salary": str(recommended),
        "range_low": str(low),
        "range_high": str(high),
        "net_income": str(net),
        "rationale": (
            f"Comparable wage {industry['title']} median ${median} × FTE {fte:.2f} = ${comparable}; "
            f"clamped to defensible share of net income ${net}."
        ),
        "disclaimer": C.DISCLAIMER,
    }


def tax_savings_report(
    client_id: str,
    entity_type: str,
    net_income: Decimal | str,
    proposed_salary: Decimal | str | None = None,
    augusta_days: int = 0,
    augusta_daily_rate: Decimal | str = "0",
    section_179: Decimal | str = "0",
    qbi_eligible_income: Decimal | str | None = None,
) -> dict[str, Any]:
    net = money(net_income)
    salary = money(proposed_salary or 0)
    augusta = money(money(augusta_daily_rate) * augusta_days)
    sec179 = money(min(money(section_179), C.SECTION_179_CAP))
    qbi_base = money(qbi_eligible_income if qbi_eligible_income is not None else max(net - salary, money(0)))

    strategies: list[dict[str, Any]] = []

    # Current liability proxy (sole prop style SE + ordinary on net)
    se_tax = money(net * C.SE_INCOME_FACTOR * C.SE_TAX_RATE) if entity_type == "sole_prop" else money(0)
    ordinary = money(net * C.ORDINARY_RATE)
    current_liability = money(se_tax + ordinary)

    optimized = current_liability
    cumulative_parts = []

    if entity_type == "s_corp" and salary > 0:
        # S-corp: payroll taxes on salary only; remainder as distribution (no SE)
        payroll = money(salary * (C.CORP_PAYROLL_TAX_EMPLOYEE + C.CORP_PAYROLL_TAX_EMPLOYER))
        ordinary_opt = money((net - salary) * C.ORDINARY_RATE) + money(salary * C.ORDINARY_RATE)
        # compare vs treating all as SE income
        all_se = money(net * C.SE_INCOME_FACTOR * C.SE_TAX_RATE) + money(net * C.ORDINARY_RATE)
        scorp_total = money(payroll + ordinary_opt)
        savings = money(max(all_se - scorp_total, money(0)))
        strategies.append(
            {
                "strategy": "S-Corp Salary Optimization",
                "savings": str(savings),
                "detail": f"Salary ${salary}; payroll tax ${payroll} vs full SE tax baseline",
            }
        )
        optimized = scorp_total
        current_liability = all_se

    if augusta_days > 0 and augusta_days <= C.AUGUSTA_MAX_DAYS and augusta > 0:
        # deductible rent reduces taxable income
        savings = money(augusta * C.ORDINARY_RATE)
        strategies.append(
            {
                "strategy": "Augusta Rule",
                "savings": str(savings),
                "detail": f"{augusta_days} days × ${money(augusta_daily_rate)} = ${augusta} rent deduction",
            }
        )
        optimized = money(optimized - savings)

    if sec179 > 0:
        savings = money(sec179 * C.ORDINARY_RATE)
        strategies.append(
            {
                "strategy": "Section 179",
                "savings": str(savings),
                "detail": f"Expensing ${sec179} (cap ${C.SECTION_179_CAP})",
            }
        )
        optimized = money(optimized - savings)

    qbi_deduction = money(qbi_base * C.QBI_RATE)
    if qbi_deduction > 0:
        savings = money(qbi_deduction * C.ORDINARY_RATE)
        strategies.append(
            {
                "strategy": "QBI Deduction (20%)",
                "savings": str(savings),
                "detail": f"20% of ${qbi_base} QBI = ${qbi_deduction} deduction",
            }
        )
        optimized = money(optimized - savings)

    total_savings = money(max(current_liability - optimized, money(0)))

    # YoY from seeded history
    history = db.list_tax_savings(client_id)
    yoy: dict[int, dict[str, Decimal]] = {}
    for row in history:
        year = int(row["tax_year"])
        yoy.setdefault(year, {})
        yoy[year][row["strategy"]] = money(row["savings"])

    years = sorted(yoy.keys())
    cumulative = []
    running: dict[str, Decimal] = {}
    for year in years:
        for strat, val in yoy[year].items():
            running[strat] = money(running.get(strat, money(0)) + val)
        cumulative.append(
            {
                "year": year,
                "by_strategy": {k: str(v) for k, v in running.items()},
                "total": str(sum(running.values(), money(0))),
            }
        )

    return {
        "current_liability": str(current_liability),
        "optimized_liability": str(max(optimized, money(0))),
        "total_savings": str(total_savings),
        "strategies": strategies,
        "cumulative_yoy": cumulative,
        "chart_current_vs_optimized": {
            "categories": ["Current", "Optimized"],
            "values": [str(current_liability), str(max(optimized, money(0)))],
        },
        "disclaimer": C.DISCLAIMER,
    }
