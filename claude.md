# Rental Property P&L Automation

## Project Purpose
Automated monthly pipeline that:
1. Reads bank/credit card transaction CSVs (Wells Fargo checking + Chase credit card)
2. Normalizes and categorizes each transaction by property and expense category
3. Pushes categorized data to a Google Sheet with per-property tabs and an aggregated P&L tab

## Architecture
- Python 3.11+ project
- Uses `gspread` library with service account auth for Google Sheets
- Uses Anthropic API (claude-haiku-4-5-20251001) for fuzzy transaction categorization
- Config-driven: all property names, categories, and known vendor mappings in a YAML config file
- CSV downloads land in `./downloads/` folder (put there by Claude in Chrome)

## Google Sheet Structure
- Spreadsheet ID: YOUR_SPREADSHEET_ID_HERE
- Sheet names (tabs): "Property 1", "Property 2", "Property 3", "P&L"
  (Replace these with your actual property names/sheet names)
- Each property sheet has identical columns:
  - Date | Description | Category | Amount | Source (Bank/CC)
- The P&L tab aggregates from all three property sheets
  (Describe your actual P&L structure here — what rows/columns it uses)

## Transaction Sources
- Wells Fargo checking CSV format: Date, Amount, *, *, Description
  (Verify and correct these column positions after your first CSV download)
- Chase credit card CSV format: Transaction Date, Post Date, Description, Category, Type, Amount
  (Verify and correct these after your first CSV download)

## Categorization Logic
1. First, check the known vendor mapping in config.yml (exact and partial matches)
2. If no match, use the Claude API (Haiku model) to classify:
   - Which property does this transaction belong to?
   - What expense category? (Mortgage, Insurance, Property Tax, HOA, Maintenance, Utilities, Property Management, Other)
3. Any transaction Claude can't confidently categorize gets flagged for manual review
4. User can add new mappings to config.yml over time to reduce API calls

## Config File (config.yml)
Should contain:
- properties: list of property names matching Google Sheet tab names
- categories: list of valid expense categories
- vendor_mappings: dict of known vendor → {property, category} mappings
- spreadsheet_id: Google Sheet ID
- downloads_dir: path to CSV download folder

## Key Behaviors
- Never overwrite existing data in the sheet — append new months only
- Before writing, check what month was last written to avoid duplicates
- Log all categorization decisions to a local CSV audit trail
- Print a summary after each run: X transactions processed, Y auto-categorized, Z flagged for review

## File Structure

rental-pnl-automation/
├── CLAUDE.md
├── config.yml                 # All configuration
├── service_account.json       # Google credentials (DO NOT commit)
├── .env                       # ANTHROPIC_API_KEY (DO NOT commit)
├── .gitignore
├── requirements.txt
├── src/
│   ├── init.py
│   ├── main.py               # Entry point / orchestrator
│   ├── csv_parser.py         # Normalize WF and Chase CSVs
│   ├── categorizer.py        # Rule-based + Claude API categorization
│   ├── sheets_writer.py      # Google Sheets read/write
│   └── models.py             # Transaction dataclass
├── downloads/                 # Where CSVs land from Claude in Chrome
├── logs/                      # Audit trail CSVs
└── tests/
├── test_csv_parser.py
├── test_categorizer.py
└── fixtures/              # Sample CSV files for testing

## Dependencies
- gspread (Google Sheets via service account)
- anthropic (Claude API for categorization)
- pyyaml (config file)
- python-dotenv (env vars)
- pandas (CSV processing)

## Error Handling
- If a CSV file can't be parsed, log the error and skip it (don't crash)
- If the Sheets API fails, retry up to 3 times with exponential backoff
- If Claude API can't categorize a transaction, flag it as "REVIEW" in the category column

## Testing
- Unit tests for CSV parsing (use fixture files with sample WF and Chase data)
- Unit tests for categorizer (mock the Claude API)
- Integration test that writes to a test Google Sheet (separate sheet ID in config)

## Web Application

### Overview
The project now includes a web interface built on the existing CLI pipeline. Both interfaces share the same core logic — the web app is a layer on top, not a rewrite.

### Tech Stack
- **Backend:** FastAPI (Python) — wraps existing pipeline modules (csv_parser, categorizer, sheets_writer)
- **Frontend:** React (Vite + TypeScript) — single-page app for transaction review and management
- **API communication:** REST JSON endpoints
- **Auth:** Google Identity-Aware Proxy (IAP) in production; simple shared password for local dev

### Web App File Structure (additions to existing project)
```
rental-pnl-automation/
├── ... (existing files unchanged)
├── api/
│   ├── __init__.py
│   ├── app.py                 # FastAPI application entry point
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── transactions.py    # Upload, list, recategorize transactions
│   │   ├── pipeline.py        # Trigger pipeline runs, check status
│   │   └── config.py          # View/edit vendor mappings and categories
│   ├── dependencies.py        # Shared dependencies (config, sheets client)
│   └── schemas.py             # Pydantic request/response models
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts      # API client (fetch wrapper)
│       ├── components/
│       │   ├── TransactionTable.tsx    # Main review table with inline editing
│       │   ├── CategorySelect.tsx      # Dropdown for category assignment
│       │   ├── PropertySelect.tsx      # Dropdown for property assignment
│       │   ├── FileUpload.tsx          # CSV upload drag-and-drop
│       │   ├── PipelineStatus.tsx      # Run status and logs
│       │   ├── VendorMappings.tsx      # View/edit vendor mapping rules
│       │   └── MonthlySummary.tsx      # Summary stats per run
│       ├── pages/
│       │   ├── ReviewPage.tsx          # Transaction review workflow
│       │   ├── DashboardPage.tsx       # Overview with monthly summary
│       │   └── SettingsPage.tsx        # Vendor mappings and config
│       ├── types/
│       │   └── index.ts               # TypeScript interfaces matching API schemas
│       └── styles/
│           └── globals.css
├── Dockerfile
├── docker-compose.yml          # Local dev with both services
└── clouddeploy/
    ├── cloudbuild.yaml         # Cloud Build config
    └── scheduler-job.json      # Cloud Scheduler config for monthly runs
```

### API Endpoints

```
GET    /api/health                        # Health check
POST   /api/transactions/upload           # Upload CSV file(s), returns parsed transactions
GET    /api/transactions?month=YYYY-MM    # List transactions for a given month
PATCH  /api/transactions/{id}             # Update category/property for a single transaction
POST   /api/transactions/bulk-update      # Batch update multiple transactions
POST   /api/pipeline/run                  # Trigger full pipeline (parse → categorize → write to sheets)
GET    /api/pipeline/status               # Check if a run is in progress, last run result
GET    /api/config/vendor-mappings        # List all vendor mappings
POST   /api/config/vendor-mappings        # Add a new vendor mapping
DELETE /api/config/vendor-mappings/{key}  # Remove a vendor mapping
GET    /api/config/categories             # List valid categories
GET    /api/config/properties             # List properties
```

### Web UI Workflow

The core user workflow is:

1. **Upload** — User uploads Wells Fargo and/or Chase CSVs (or they arrive via Claude in Chrome)
2. **Review** — Transactions appear in a table. Auto-categorized rows show green. Uncertain rows (flagged "REVIEW") show yellow and are sorted to the top.
3. **Fix** — User clicks on any transaction to change its property or category via dropdown. Can also click "Add Mapping" to save a new vendor rule so future transactions auto-categorize.
4. **Push** — User clicks "Push to Google Sheets" to write finalized transactions. Shows a confirmation summary before writing.
5. **Dashboard** — Shows monthly summary stats: total expenses per property, category breakdown, count of manual vs auto categorizations.

### Frontend Design Guidelines
- Clean, minimal UI — use Tailwind CSS for styling
- Mobile-responsive (wife may access from phone)
- Transaction table should support sorting by date, property, category, amount
- Use color coding: green = auto-categorized, yellow = needs review, blue = manually edited
- Show toast notifications for success/error states
- No complex state management library needed — React useState/useContext is sufficient

### Backend Design Guidelines
- FastAPI app imports and calls existing functions from src/ — does NOT duplicate logic
- All state lives in Google Sheets (no local database) — the app reads from and writes to the sheet
- Pipeline runs are synchronous for now (transactions are small enough)
- Store uploaded CSVs temporarily in /tmp during processing
- CORS configured to allow frontend origin in dev and production

---

## Docker & Cloud Run Deployment

### Docker Setup
- Single Dockerfile that builds the React frontend, then serves it via FastAPI's static file mounting
- Multi-stage build: Node stage builds the frontend, Python stage runs the API and serves static files
- service_account.json is NOT baked into the image — it's mounted as a secret at runtime

### Dockerfile Design
```
Stage 1: Node — install deps, build React → produces dist/
Stage 2: Python 3.11-slim — install pip deps, copy src/ and api/, copy frontend dist/, run uvicorn
```

### Environment Variables (Cloud Run)
```
ANTHROPIC_API_KEY          # From Secret Manager
GOOGLE_SHEETS_SPREADSHEET_ID  # From config or env
PORT                       # Set by Cloud Run (default 8080)
```

### Google Cloud Deployment

**Services used:**
- **Cloud Run** — hosts the web app container (scales to zero when not in use)
- **Artifact Registry** — stores Docker images
- **Cloud Scheduler** — triggers monthly pipeline runs via HTTP POST to /api/pipeline/run
- **Secret Manager** — stores Anthropic API key and service account JSON
- **Identity-Aware Proxy (IAP)** — restricts access to allowed Google accounts only

**Cloud Run configuration:**
- Region: us-central1 (or closest to you)
- Min instances: 0 (scale to zero)
- Max instances: 1 (personal use, no need for scaling)
- Memory: 512MB
- CPU: 1
- Request timeout: 300s (pipeline runs may take a minute)
- Allow unauthenticated: No (IAP handles auth)

**IAP Setup:**
- Enable IAP on the Cloud Run service
- Add your and your wife's Gmail addresses as IAP-secured Web App Users
- This means you both log in with your Google accounts — no shared passwords

**Cloud Scheduler (monthly automation):**
- Schedule: `0 10 3 * *` (3rd of every month at 10am)
- Target: HTTP POST to `https://YOUR_CLOUD_RUN_URL/api/pipeline/run`
- Auth: OIDC token with service account credentials
- This replaces the local cron job

### Deployment Commands (reference for Claude Code)
```bash
# Build and push Docker image
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT_ID/REPO_NAME/rental-pnl

# Deploy to Cloud Run
gcloud run deploy rental-pnl \
  --image REGION-docker.pkg.dev/PROJECT_ID/REPO_NAME/rental-pnl \
  --region us-central1 \
  --allow-unauthenticated=false \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest" \
  --set-secrets="/secrets/service_account.json=sheets-service-account:latest" \
  --memory=512Mi \
  --max-instances=1 \
  --min-instances=0

# Set up Cloud Scheduler
gcloud scheduler jobs create http rental-pnl-monthly-run \
  --schedule="0 10 3 * *" \
  --uri="https://YOUR_CLOUD_RUN_URL/api/pipeline/run" \
  --http-method=POST \
  --oidc-service-account-email=SERVICE_ACCOUNT_EMAIL
```

---

## CLI and Web Coexistence

The CLI (src/main.py) continues to work as before. The web app (api/app.py) imports from the same src/ modules. Both share:
- config.yml for settings
- src/csv_parser.py for parsing
- src/categorizer.py for categorization
- src/sheets_writer.py for Google Sheets operations

The only difference is that the web app adds a review/edit step between categorization and writing to sheets, while the CLI writes immediately (flagging uncertain ones as "REVIEW" in the sheet).

