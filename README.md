# Lifecycle Platform

## Setup

### Prerequisites

- Python 3.12+
- LocalGCP (for local BigQuery emulation): https://localgcp.com/
- Colima (Docker backend for macOS)

```bash
# Install LocalGCP
brew install slokam-ai/tap/localgcp

# Install Colima (if not installed)
brew install colima

# Start Colima (Docker backend)
colima start --vm-type=qemu

# Start BigQuery emulator (requires Docker)
localgcp up --services=bigquery

# Install Python dependencies
pip install -e .
```

### Database Setup

The platform separates schema initialization from seed data:

```bash
# Production mode (schema only - safe for Airflow)
python -m src.lifecycle_platform.database --mode production

# Development mode (schema + seed data) this is for first time setup or testing.
python -m src.lifecycle_platform.database --mode development
```

**Important:** Seed data never loads automatically. Only use `setup_for_development()` for local development/demo.

## Run Tests

```bash
pytest tests/
```

## Project Structure

```
.
├── sql/
│   ├── schema.sql          # Table definitions (CREATE IF NOT EXISTS)
│   ├── init_schema.sql    # Schema only (for Airflow init task)
│   ├── seed_data.sql      # Sample data (dev only)
│   └── audience_query.sql # Audience segmentation query
├── src/lifecycle_platform/
│   ├── database.py       # Database operations
│   └── pipeline.py     # Campaign pipeline
├── tests/
│   └── test_pipeline.py
├── skills/
│   ├── pr-reviewer/     # Code review skill
│   └── unit-test/       # Unit test skill
├── agents/             # AI agent definitions
├── ai-session/          # AI usage log
└── pyproject.toml
```

## Database Functions

| Function | Purpose | Auto-run |
|----------|---------|---------|
| `initialize_schema()` | Create tables | No |
| `load_seed_data()` | Load demo data | No |
| `setup_for_development()` | Dev setup | Manual |
| `run_audience_query()` | Run query | Yes |

## Assumptions

- LocalGCP runs on localhost:9060
- Colima must be running for Docker-based services
- Tables use `CREATE TABLE IF NOT EXISTS` (idempotent)
- Seed data loads only when explicitly requested

## Design Decisions

1. **Separate init from seed** - Seed data never auto-loads, safe for production
2. **LEFT JOIN + GROUP BY** - Efficient for counting searches per renter
3. **NOT EXISTS** - Cleaner than LEFT JOIN + IS NULL for suppression exclusion
4. **EPOCH calculation** - LocalBQ compatible alternative to TIMESTAMP_DIFF
