# Lifecycle Platform

Automated SMS reactivation pipeline with BigQuery audience segmentation, ESP batching/deduplication, Airflow orchestration, and observability design.

## Coverage

- **Part 1:** Audience segmentation SQL in `src/sql/audience_query.sql`
- **Part 2:** ESP batching, retry, deduplication, and failure logging in `src/pipeline.py`
- **Part 3:** Airflow DAG in `dags/sms_reactivation_dag.py`; Task 1 exports the audience to `sms_reactivation_audience_staging`
- **Part 4:** Value model integration design in `part4_value_model_integration.md`
- **Part 5:** Observability design in `part5_observability_design.md`
- **AI Usage Log:** `ai-session/`

## Quick Start

Requirements: Python 3.12+, Docker/Colima, and LocalGCP's BigQuery emulator.

```bash
brew install slokam-ai/tap/localgcp
colima start --vm-type=qemu
localgcp up --services=bigquery

pip install -e .
docker-compose up -d
```

Open Airflow at `http://localhost:8080`. The DAG includes a `database_provisioning` task that creates required tables and loads local seed data only when the demo tables are empty.

## Run Tests

```bash
pytest tests/
```

## Expected Demo Result

The seed data produces **2 eligible renters**:

- `renter_001`
- `renter_002`

The audience is exported to `sms_reactivation_audience_staging` before validation and send. See `working_logic.md` for the full seed-data walkthrough.

## Key Design Decisions

- **Idempotent provisioning:** Airflow creates schema every run and only loads local seed data when tables are empty.
- **Stable audience query:** Date logic anchors to `CURRENT_DATE()` so same-day reruns return the same audience.
- **ESP interface preserved:** `execute_campaign_send()` accepts any client with `send_batch(campaign_id, recipients)`. The included `ESPClient` is a safe local stub.
- **File-based deduplication:** Uses `sent_renters.json` for the local implementation; production design moves this to a durable send log table.
- **Airflow parse-time hygiene:** Heavy BigQuery/project imports live inside task functions to avoid DagBag import timeouts.

## Project Structure

```
src/sql/audience_query.sql          # Audience segmentation
src/sql/schema.sql                  # Tables, staging, reporting
src/sql/seed_data.sql               # Local demo data
src/pipeline.py                     # ESP send pipeline
src/repository.py                   # BigQuery repository + staging export
dags/sms_reactivation_dag.py        # Airflow DAG
dags/helpers.py                     # Validation, reporting, Slack helpers
part4_value_model_integration.md    # Model score design
part5_observability_design.md       # Datadog/alerting/recovery design
working_logic.md                    # Seed data explanation
ai-session/                         # AI usage log
```

## Assumptions

- LocalGCP runs the BigQuery emulator locally.
- `.env.example` contains local-only placeholder values.
- The ESP integration is represented by a stub client because no real ESP endpoint was provided.

## Future Improvements

- Replace the demo LocalGCP setup with managed BigQuery datasets and service accounts.
- Replace the local ESP stub with a real HTTP client and request-level idempotency keys.
- Move send logs and failed batches from local files to BigQuery tables.
- Add real Datadog metric emission for the observability design and even slack alerts.
