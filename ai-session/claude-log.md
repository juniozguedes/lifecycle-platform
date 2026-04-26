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