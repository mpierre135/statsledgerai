# Superprompt: Build StatsLedger AI (Automated Bookkeeping & Tax Prep App)

Copy and paste the entire block below into Claude (or another LLM) to generate a complete, working prototype or full-stack codebase for **StatsLedger AI**. This prompt is meticulously engineered to instruct Claude to build a production-ready application based on the advanced workflow concepts popularized by Jason Stats on his channel *Jason On Firms*.

***

```markdown
You are a Staff Software Engineer and Principal Software Architect specializing in modern fintech, AI-driven accounting tech, and beautiful, high-utility web applications. 

Your goal is to build a complete, highly-functional, and production-grade prototype for **StatsLedger AI**—an AI-first, subscription-free, automated bookkeeping and tax preparation application designed for progressive accounting firms. The app's core philosophy is to escape the "tyranny of QuickBooks Online subscriptions" by combining a flat-file double-entry database backend with an intelligent automation and client collaboration layer.

### Brand & Design System
- **Theme**: Premium modern SaaS, clean, highly-trustworthy, and slightly nerdy.
- **Color Palette (60-30-10 Rule)**:
  - **Dominant (60%)**: Dark Slate/Deep Navy backgrounds (`#0F172A` to `#1E293B`) for a premium professional feel, with pure white and light grey for workspace text.
  - **Secondary (30%)**: Cool Grey and Clean White (`#F8FAFC`, `#FFFFFF`) for clean card layouts, crisp tables, and structured grids.
  - **Accent (10%)**: Vibrant Mint Green (`#10B981` / `#34D399`) for successful matches, balanced ledgers, and completed tasks; deep alert Amber (`#F59E0B`) for low-confidence transactions needing review.
- **Typography**: Clean, highly readable sans-serif (Inter/system-ui) with monospace font styling for ledger amounts and transaction databases.

---

### Core App Architecture & Modules
You must generate a complete, working implementation using **Python (FastAPI) and React (Vite + Tailwind CSS + Lucide Icons)** OR a beautifully unified **Python Streamlit Application** that simulates this full end-to-end flow. Provide the entire directory structure, data schemas, and fully fleshed-out code for each of the following 6 modules:

#### Module 1: FLAT-FILE DOUBLE-ENTRY LEDGER (The "Bean Count" Backend)
- **Concept**: Instead of a heavy relational database or expensive subscriptions, use an open-source text-based ledger format (inspired by `beancount`).
- **Core Functionality**:
  - Implement a Python-based parser/writer that reads/writes transactions to a flat `.beancount` text file.
  - Support standard Double-Entry rules: Assets, Liabilities, Equity, Income, Expenses. All transactions must balance (Debits = Credits).
  - Include multi-dimensional tagging categories for Class and Location tracking to support clients with "lemonade stands, rental properties, and G-Wagons" within a single workspace.
  - Export the live trial balance to standard CSV/Excel format.

#### Module 2: THE THREE-LAYER CAKE AUTOCLASSIFICATION ENGINE
- **Concept**: Emulate the classification model of *Digits* to achieve high-accuracy automated bookkeeping.
- **Core Functionality**:
  - Implement a classification algorithm that tries to code transactions using three cascading models:
    1. **Layer 1: The Client Model**: Checks the company's historical `.beancount` ledger files. If a similar transaction (similar description, merchant, or amount) was coded in the past, match it.
    2. **Layer 2: The Firm Model**: Falls back to how the accounting firm has coded this specific merchant/vendor across *all other* clients in their firm directory.
    3. **Layer 3: The Global User Model**: Falls back to a standard industry dictionary (e.g., standard QuickBooks chart of accounts) to guess the category based on semantic mapping.
  - Returns a "Confidence Score" (0-100%). Transactions below 85% confidence are flagged as "Uncategorized" and automatically pushed to the review inbox.

#### Module 3: AUTO-CLOSE & QUALITY ASSURANCE (The "Keeper/Double" Layer)
- **Concept**: Month-end close automation that sits above the ledger to spot anomalies.
- **Core Functionality**:
  - **Payee Grouping View**: Instead of reviewing transactions sequentially, group them by Payee/Merchant to instantly catch inconsistencies.
  - **Anomaly Detection Dashboard**: Automatically run checks and flag:
    1. **Negative Bank Balances**: Cash/Bank account dropping below zero.
    2. **Multi-Category Inconsistencies**: Same vendor (e.g., Amazon) mapped to different expense accounts (e.g., Office Supplies vs. Cost of Goods Sold) within the same period without explanation.
    3. **Missing Descriptions**: Transactions over $1,000 missing receipts or business descriptions.
    4. **Parent-Level Booking**: Transactions posted to parent accounts instead of specific sub-accounts.
  - **Automated Accruals Engine ("Acruer" style)**: A parser that detects descriptions containing `"for the period [date] to [date]"` (or let users tag them) and automatically generates monthly accrual/prepaid amortization schedules and journal entries.

#### Module 4: THE UNCAT MAGIC-LINK PORTAL
- **Concept**: Zero-friction client collaboration. No username, no password, just a secure, temporary token-based URL (magic link).
- **Core Functionality**:
  - Generates a "Client View" of the portal containing only "Uncategorized" or "Needs Info" transactions flagged by Module 2 and 3.
  - Clients can:
    - Type descriptions/memos (e.g., "This was for the client lunch at Steve's").
    - Suggest or pick categories from a simplified, non-technical dropdown.
    - Upload receipts (PDF/PNG).
  - Simulate an AI Vision feature that reads the uploaded receipt, extracts the merchant, date, and amount, and matches it back to the transaction in the ledger (automatically attaching the file path).
  - When approved by the bookkeeper, these changes are written directly to the `.beancount` file.

#### Module 5: PRE-ACCOUNTING & TAX PREP ASSISTANCE (The "Sorban/Stanford Tax" Layer)
- **Concept**: Bridge the gap between daily bookkeeping and the tax return.
- **Core Functionality**:
  - **Prior-Year Ingest**: Upload a prior-year tax return PDF/JSON (or mock its data). The app extracts past W-2s, 1099s, and Schedules to dynamically generate a custom client questionnaire and document request checklist.
  - **AI Doc Sorter**: Provide a file upload zone. Simulate an AI vision engine that takes a bulk PDF upload, splits it into individual documents, and auto-detects form types (e.g., W-2, 1099-INT, 1099-NEC), automatically checking off the corresponding checklist item.
  - **Book-To-Tax Mapping Grid**: Present a mapping table where the double-entry Chart of Accounts (COA) is mapped to tax schedule lines (e.g., "Advertising" maps to Schedule C, Line 8; "Meals" maps to Schedule C, Line 24b with a built-in 50% M&E limitation calculator).
  - **Workpaper Generator**: Compile all categorized transactions, journal adjustments, and source document links into an organized "Tax Prep Lead Sheet" (CSV/Excel workbook) formatted for direct import into tax software (Lacerte/UltraTax/Drake).

#### Module 6: HIGH-MARGIN ADVISORY CORE (The "Corvee/HolistaPlan" Layer)
- **Concept**: Monetize your expertise through clean visual reporting rather than raw tax forms.
- **Core Functionality**:
  - **Reasonable Comp Calculator**: A structured wizard that runs a business owner's net income, hours worked, and industry trade through a formula to output a defensible "S-Corp Reasonable Salary" figure (avoiding audit risk).
  - **Visual Tax Savings Report**: Generate a beautiful, client-friendly dashboard displaying "Cumulative Year-over-Year Tax Savings" from various strategies (e.g., Augusta Rule, S-Corp Salary optimization, QBI deduction, Section 179 depreciation). Provide charts visualizing "Current Tax Liability" vs "Optimized Tax Liability".

---

### Technical Implementation & Deliverable
Provide a fully functioning, self-contained implementation. 

If writing a **Python Streamlit Application**, organize it with clear tabs corresponding to the 6 modules, using dummy data generators to allow immediate interaction. Store the state in Streamlit's `session_state` to let transactions flow from bank uploads to Uncat portals, then to the Close check, and finally to the Tax Mapping and Advisory dashboard.

Ensure the code:
1. Is complete, containing no placeholders, "TODOs," or truncated snippets.
2. Contains robust calculations (e.g., actual balancing of debits/credits in double-entry, real S-Corp salary calculations, real book-to-tax meal limits).
3. Utilizes Tailwind-like styling or customized CSS inside Streamlit to match the "Dark Slate + Mint Green" premium brand identity.
4. Generates sample `.beancount` syntax text strings in the Flat-File ledger module to show exactly how data is kept on the machine.

Let's build a software marvel that makes accountants look like tech-enabled superheroes!
```
***

Use the prompt above to bring the application to life. It captures the entire soul of the channel's modern, tech-enabled, high-margin, and highly automated accounting philosophy.
