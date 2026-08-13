# StatsLedger AI

AI-first, subscription-free automated bookkeeping and tax prep for progressive accounting firms.

Flat-file **beancount** ledgers + SQLite app state + FastAPI + React (Vite, Tailwind, Lucide).

## Quick start

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

Or separately:

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.
python -m app.seed
uvicorn app.main:app --reload --port 8000

# Frontend (another terminal)
cd frontend
npm install
npm run dev
```

- Firm workspace: http://127.0.0.1:5173  
- API: http://127.0.0.1:8000/api/health  
- Sample bank CSV: `data/samples/harbor_bank_may2025.csv`

## Modules

1. **Ledger** — append-only `.beancount` with class/location tags, trial balance, CSV/XLSX export  
2. **Three-layer classifier** — client → firm → global dictionary with explainable confidence  
3. **Close & QA** — payee groups, anomalies, Needs Info handoff, period lock, accrual schedules  
4. **Magic-link portal** — hashed tokens, staged edits, receipt upload (simulated vision)  
5. **Tax prep** — prior-year ingest, doc sorter, book-to-tax (50% M&E), lead sheet workbook  
6. **Advisory** — S-Corp reasonable comp + current vs optimized / YoY savings charts  

## Tests

```bash
cd backend
source .venv/bin/activate
export PYTHONPATH=.
pytest -q
```

## Design

Dark slate (`#0F172A` / `#1E293B`) with mint (`#10B981`) success accents and amber (`#F59E0B`) for low-confidence review. Inter + JetBrains Mono for amounts.

## Philosophy

- Ledger text is the accounting source of truth (never regenerated from the AST).  
- Client portal submissions never touch `.beancount` until a bookkeeper approves.  
- Money is `Decimal` only — floats are rejected.
