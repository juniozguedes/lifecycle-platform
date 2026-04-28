# AI Session Log

## Session Date: 2026-04-25

### Tools Used
- OpenCode (orchestrator agent)
- Web search

### Context
Setting up the Lifecycle Platform.

### Decisions

1. **Database**: Decided to use BigQuery (not SQLite) because:
   - Schema uses BigQuery types (STRING, TIMESTAMP)
   - Part 4 depends on BigQuery ML table
   - Job likely uses BigQuery in production

2. **Local Setup**: Installed LocalGCP for BigQuery emulation
   - Running on localhost:9060
   - DuckDB-backed, works offline

### Next Steps
- LocalGCP is running in foreground
- Need to create schema + sample data for candidates
- Will provide setup instructions in README

---

## Session: Project Setup (2026-04-25)

### Actions Taken

1. **Initialized project structure** with mise + Poetry
2. **Created SQL schema** for 3 tables + ML predictions table
3. **Created seed data** with edge cases (10 renters, various scenarios)
4. **Created audience query** following Part 1 criteria
5. **Created Python database module** for queries

### Files Created

- `mise.toml` - mise config with BigQuery endpoint
- `pyproject.toml` - Poetry project
- `sql/schema.sql` - Table definitions
- `sql/seed_data.sql` - Sample data
- `sql/audience_query.sql` - Part 1 solution
- `src/lifecycle_platform/database.py` - Python query helpers
- `README.md` - Setup instructions

### Query Logic

The audience query implements all 8 criteria:
1. `last_login < ... INTERVAL 30 DAY`
2. `subscription_status = 'churned'`
3. `COUNT >= 3` (HAVING clause)
4. `phone IS NOT NULL`
5. `sms_consent = TRUE`
6. `NOT EXISTS (suppression_list)`
7. `dnd_until IS NULL OR < CURRENT_TIMESTAMP()`
8. Uses `CURRENT_TIMESTAMP()` for idempotency

### Edge Cases Covered in Seed Data

- In-scope: churned, >30 days, 3+ searches, phone, sms_consent, not suppressed
- Excluded: active subscription, dnd in future, <30 days ago, never_subscribed
- Suppressed: renter_003, renter_008

### Commit (2026-04-25)

- Initial commit: `feat: initial lifecycle_platform setup with BigQuery schema and audience query`
- Pushed to: `main` branch
- Fix applied: TIMESTAMP_DIFF (cleaner for TIMESTAMP types)

### Session: Part 2 Pipeline (2026-04-25)

#### Actions Taken

1. **Created pipeline orchestration** (`src/lifecycle_platform/pipeline.py`)
2. **Implemented all Part 2 requirements**:
   - Batching (max 100 recipients)
   - Exponential backoff with jitter (max 5 retries)
   - Deduplication (file-based sent_log)
   - Error handling (failed batches logged)
   - Metrics (total_sent, total_failed, total_skipped, elapsed_seconds)
3. **Created unit tests** (4 tests, all passing)

#### Files Created

- `src/lifecycle_platform/pipeline.py` - Campaign execution module
- `tests/test_pipeline.py` - Unit tests

#### Commit (2026-04-25)

- `feat: add pipeline orchestration with batching, retry, and dedup`

---

## Session: Code Audit & Fixes (2026-04-25)

#### PR Review Actions

Invoked `pr-reviewer` and `unit-test` skills to audit code.

**Issues Found:**

| File | Issue |
|------|-------|
| `pipeline.py` | Line 83: `except Exception` catch-all — too broad |
| `pipeline.py` | Line 123: fragile `last_error in locals()` check |
| `pipeline.py` | Missing return type on `save_failed_batch` |
| `database.py` | Missing `Optional` import for type annotation |
| `tests/test_pipeline.py` | Uses `print()` for assertions instead of pytest |

#### Fixes Applied

1. Added `Optional` import to `pipeline.py`
2. Specific exception handling: `ConnectionError`, `TimeoutError`, `OSError` for retries
3. Return 3-tuple from `send_batch_with_retry`: `(batch, success, error_msg)`
4. Fixed error message: `error_msg or "unknown_error"`
5. Added `Optional` import to `database.py`, fixed type annotation
6. Rewrote tests in proper pytest style with classes

#### Test Coverage Added

- `TestCreateBatches` (3 tests)
- `TestRetryWithBackoff` (2 tests)
- `TestLoadSentLog` (3 tests)
- `TestExecuteCampaignSend` (4 tests)

**Result: 12 tests, all passing**

---

## Session: Skills & AGENTS.md (2026-04-26)

#### Actions Taken

1. **Copied skills to project**:
   - `skills/pr-reviewer/skill.md` - Code review skill
   - `skills/unit-test/skill.md` - Unit test skill

2. **Created project AGENTS.md** with:
   - Global coding standards
   - Project-specific Lifecycle Platform details
   - Tech stack, architecture, local development commands
   - Skills invocation guide
   - Database schema
   - Campaign pipeline parts

---

## Session: Verification (2026-04-26)

#### Actions Taken

1. **Added ESPClient class** to `pipeline.py`:
   - Was missing the interface for ESPClient
   - Now matches exactly: `class ESPClient: def send_batch(...)`
   
2. **Refactor and check system requirements** via backend agent:
   - Batching: 100 max ✓
   - Rate Limiting: 429 + backoff + jitter ✓
   - Deduplication: file-based ✓
   - Error Handling: log failed, continue ✓
   - Metrics: 4 keys ✓

#### Tests
- 12 tests passing

---

## Session: BigQuery Setup & Production Ready (2026-04-27)

### Issue Encountered

LocalGCP requires Docker. Docker wasn't running — Colima (Docker backend) was not started.

### Solution

Started Colima with qemu driver (vz was failing):
```bash
colima start --vm-type=qemu --cpu 1 --memory 2
localgcp up --services=bigquery
```

### Actions Taken

1. **Fixed DuckDB compatibility**:
   - `TIMESTAMP_DIFF` not supported → used `EPOCH()` calculation
   - `CURRENT_TIMESTAMP()` → `CURRENT_TIMESTAMP::TIMESTAMP`

2. **Made database setup production-ready**:
   - Removed all DROP statements from schema.sql
   - Added `CREATE TABLE IF NOT EXISTS` for idempotent creation
   - Created `sql/init_schema.sql` (schema only)
   - Separated functions:
     - `initialize_schema()` — production (schema only)
     - `load_seed_data()` — dev only, never auto
     - `setup_for_development()` — dev setup (schema + seed)
     - `run_audience_query()` — production query

3. **Updated CLI support**:
   - `--mode production` — schema only
   - `--mode development` — schema + seed data

4. **End-to-end test verified**:
   - BigQuery query works
   - Pipeline sends successfully
   - 12 tests passing

### Files Changed

- `sql/schema.sql` — removed DROP, added IF NOT EXISTS
- `sql/init_schema.sql` — new file (schema only)
- `sql/audience_query.sql` — EPOCH calculation
- `src/lifecycle_platform/database.py` — separated functions
- `README.md` — updated documentation

---

## Session: Repository Pattern & Linting (2026-04-27)

### Actions

1. **Refactored to repository pattern**:
   - Created `repository.py` with `AudienceRepository` class
   - Separated business logic from infrastructure
   - Clean import in `database.py` (inside __main__)

2. **Fixed DRY violation**:
   - Removed duplicate `load_sql_file()` from repository.py
   - Now imports from `database.py`

3. **Updated DRY in AGENTS.md**:
   - Global: `~/.config/opencode/AGENTS.md`
   - Project: `lifecycle-platform/AGENTS.md`

4. **Added linting with Ruff**:
   - Added ruff to pyproject.toml
   - Added lint tasks to mise.toml
   - Fixed 12 lint errors
   - All lint checks pass

### Files Changed

- `src/lifecycle_platform/repository.py` - NEW
- `src/lifecycle_platform/database.py` - refactored
- `pyproject.toml` - added ruff
- `mise.toml` - added lint tasks
- `AGENTS.md` (both) - added DRY principle

### Tests
12 passing

---

## Session: Restructure & Airflow Integration (2026-04-28)

### Actions Taken

1. **Restructured codebase**:
   - Moved `src/lifecycle_platform/` → `src/`
   - Added `dags/` for Apache Airflow
   - Added `docker-compose.yml` for local dev (with env vars, no hardcoded secrets)
   - Added `.env.example` template

2. **Created Airflow DAG** (`dags/sms_reactivation_dag.py`):
   - Daily SMS reactivation campaign
   - Tasks: query → validate → send → report
   - Slack notifications for success/failure
   - BigQuery reporting table integration

3. **PR Review fixes**:
   - Fixed type annotation on `execute_campaign_send()`
   - Removed duplicate `src/sql/init_schema.sql`
   - Fixed misleading log message in helpers.py

4. **Security fix**:
   - Removed hardcoded secrets from docker-compose.yml
   - Now uses environment variables via .env file
   - Added .env to .gitignore

### Files Changed

- `src/database.py` - moved from lifecycle_platform
- `src/pipeline.py` - moved from lifecycle_platform  
- `src/repository.py` - moved from lifecycle_platform
- `dags/sms_reactivation_dag.py` - NEW (Airflow DAG)
- `dags/helpers.py` - NEW (Slack + validation helpers)
- `docker-compose.yml` - NEW (uses env vars)
- `.env.example` - NEW (template)
- `poetry.lock` - NEW
- `AGENTS.md` - updated architecture
- `.gitignore` - updated with .env

### Tests
12 passing