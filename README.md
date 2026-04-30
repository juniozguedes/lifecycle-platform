# Lifecycle Platform

Automated SMS reactivation pipeline for the lifecycle platform challenge.

## Dev cycle plan:

- **Part 1:** Audience segmentation SQL in `src/sql/audience_query.sql`
- **Part 2:** ESP batching, retry, deduplication, and failure logging in `src/pipeline.py`
- **Part 3:** Airflow DAG in `dags/sms_reactivation_dag.py`; Task 1 exports the audience to `sms_reactivation_audience_staging`
- **Part 4:** Value model integration design in `part4_value_model_integration.md`
- **Part 5:** Observability design in `part5_observability_design.md`
- **AI Usage Log:** `ai-session/`

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

## Run with Docker (Airflow)

```bash
# Copy environment template and edit with your values
cp .env.example .env  # Or create your own with real keys

# Generate secure keys for production:
# python -c "import secrets; print(secrets.token_hex(32))"

# Start Airflow
docker-compose up -d

# Access UI at http://localhost:8080
# Default credentials: admin / admin (or from .env)
```

The DAG includes a `database_provisioning` task that creates the required tables automatically. In local/demo mode, it also loads seed data only when `renter_profiles` is empty, so repeated runs remain idempotent.

### Security Warning

The default `.env.example` and `.env` file contains placeholder values for **local testing only**.

**Not suitable for production!** The placeholder keys are:
- NOT cryptographically secure
- Publicly known (not secret)

For production, generate real keys:
```bash
FERNET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

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
├── src/
│   ├── database.py       # BigQuery client + schema/seed setup
│   ├── repository.py     # Audience query repository
│   └── pipeline.py       # ESP send pipeline
├── dags/
│   ├── sms_reactivation_dag.py
│   └── helpers.py
├── tests/
│   └── test_pipeline.py
├── part4_value_model_integration.md
├── part5_observability_design.md
├── working_logic.md     # Seed/query result explanation
├── ai-session/          # AI usage log
└── pyproject.toml
```

## Database Functions

| Function | Purpose | Auto-run |
|----------|---------|---------|
| `initialize_schema()` | Create tables | Yes, through Airflow provisioning |
| `load_seed_data()` | Load demo data if empty | Yes, through Airflow provisioning |
| `setup_for_development()` | Dev setup helper | Not required for normal run |
| `run_audience_query()` | Run query | Yes |

## Assumptions

- LocalGCP runs on localhost:9060
- Colima must be running for Docker-based services
- Tables use `CREATE TABLE IF NOT EXISTS` (idempotent)
- Airflow provisioning creates schema and loads seed data only when the local demo tables are empty

## Design Decisions

1. **Idempotent provisioning** - Airflow creates schema every run and only loads local seed data when tables are empty
2. **LEFT JOIN + GROUP BY** - Efficient for counting searches per renter
3. **NOT EXISTS** - Cleaner than LEFT JOIN + IS NULL for suppression exclusion
4. **EPOCH calculation** - LocalBQ compatible alternative to TIMESTAMP_DIFF
5. **ESPClient interface preserved** - `execute_campaign_send()` accepts any client with `send_batch(campaign_id, recipients)`, while the local `ESPClient` is a safe stub for demo runs
6. **File-based deduplication** - Uses `sent_renters.json` for the poc; production design moves this to a durable send log table
7. **Airflow parse-time hygiene** - Heavy project imports that load BigQuery/google client code are imported inside task functions, so the DAG file remains fast to parse and avoids DagBag import timeouts

## Future improvements

- Replace the demo LocalGCP setup with managed BigQuery datasets and service accounts.
- Replace the local ESP stub with a real HTTP client and request-level idempotency keys.
- Move send logs and failed batches from local files to BigQuery tables.
- Add real Datadog metric emission for the observability design and even slack alerts.
