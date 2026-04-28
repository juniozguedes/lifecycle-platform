# SMS Reactivation DAG Documentation

## Table of Contents

1. [Overview](#overview)
2. [Schedule & SLA](#schedule--sla)
3. [Task Flow Diagram](#task-flow-diagram)
4. [Detailed Task Documentation](#detailed-task-documentation)
5. [Configuration Constants](#configuration-constants)
6. [Error Handling](#error-handling)
7. [Retry Policy](#retry-policy)
8. [Local Development](#local-development)

---

## Overview

The **SMS Reactivation DAG** (`sms_reactivation`) is an Apache Airflow pipeline that orchestrates a daily SMS reactivation campaign for dormant renters in the lifecycle platform. The DAG identifies eligible recipients from BigQuery, validates the audience for anomalies and data quality, executes the campaign sends via an Email Service Provider (ESP), and logs results to both BigQuery and Slack.

### Pipeline Purpose

- **Target Audience**: Dormant renters who have been identified as eligible for reactivation campaigns
- **Goal**: Re-engage users who have become inactive through targeted SMS communications
- **Integration Points**: BigQuery for data storage/querying, ESP for message delivery, Slack for notifications

### Source Files

| File | Description |
|------|-------------|
| `dags/sms_reactivation_dag.py` | Main DAG definition with all four tasks |
| `dags/helpers.py` | Helper functions for validation, logging, and notifications |
| `src/repository.py` | `AudienceRepository` for querying eligible recipients |
| `src/pipeline.py` | `execute_campaign_send()` and `ESPClient` for campaign execution |
| `src/database.py` | BigQuery client initialization and SQL file loading |

---

## Schedule & SLA

### Schedule

- **Cron Expression**: `0 5 * * *` (Daily at 5:00 AM UTC)
- **Start Date**: January 1, 2025
- **Catchup**: Disabled (`catchup=False`) to prevent backfilling old runs

### SLA (Service Level Agreement)

- **Execution Window**: Must complete within **3 hours** from start
- **SLA Deadline**: 8:00 AM UTC (3 hours after start)
- **Timeout**: Each task is subject to the overall 3-hour execution timeout
- **Max Active Runs**: 1 (prevent concurrent executions)
- **Max Active Tasks**: 1 (linear pipeline, one task at a time)

### Timing Summary

| Parameter | Value | Description |
|-----------|-------|-------------|
| Schedule | `0 5 * * *` | Runs daily at 5:00 AM UTC |
| SLA Hours | 3 | Must complete by 8:00 AM UTC |
| Start Date | 2025-01-01 | DAG activation date |
| Max Active Runs | 1 | No parallel executions |

---

## Task Flow Diagram

```
┌─────────────────────┐
│  run_audience_query │
│  (Task 1)           │
└─────────┬───────────┘
          │
          │ XCom: audience_data
          │ {recipients, count, query_timestamp}
          ▼
┌─────────────────────┐
│   validate_audience │─────► Alert on validation failure
│   (Task 2)          │
└─────────┬───────────┘
          │
          │ XCom: validation_result
          │ {is_valid, audience_count, audience, error_message}
          ▼
┌─────────────────────┐
│ execute_campaign_send│
│   (Task 3)          │
└─────────┬───────────┘
          │
          │ XCom: campaign_result
          │ {total_sent, total_failed, total_skipped, elapsed_seconds}
          ▼
┌─────────────────────┐
│log_results_and_notify│
│   (Task 4)          │
└─────────────────────┘
```

### Flow Description

The DAG follows a **linear pipeline** pattern where each task depends on the successful completion of the previous task:

1. **Task 1** queries BigQuery for eligible recipients
2. **Task 2** validates audience size, data integrity, and detects anomalies
3. **Task 3** executes the campaign send via ESP (if validation passes)
4. **Task 4** logs results to BigQuery reporting table and sends Slack notification

---

## Detailed Task Documentation

### Task 1: `run_audience_query`

**Purpose**: Execute BigQuery audience query to identify eligible recipients for the SMS reactivation campaign.

**Function Called**: 
- `AudienceRepository.get_eligible_recipients()` from `src/repository.py`

**Implementation Location**: `dags/sms_reactivation_dag.py`, lines 122-162

**Process**:
1. Initialize BigQuery client using `get_bigquery_client()`
2. Create `AudienceRepository` instance
3. Execute the audience query defined in `sql/audience_query.sql`
4. Return eligible recipients with metadata

**Output** (XCom key: `audience_data`):

| Field | Type | Description |
|-------|------|-------------|
| `recipients` | `list[dict]` | List of recipient records with `renter_id`, `phone`, etc. |
| `count` | `int` | Total number of eligible recipients |
| `query_timestamp` | `str` | ISO timestamp of query execution |

**Example Output**:
```python
{
    "recipients": [
        {"renter_id": "ABC123", "phone": "+1234567890", ...},
        {"renter_id": "DEF456", "phone": "+0987654321", ...}
    ],
    "count": 5000,
    "query_timestamp": "2025-01-15T05:15:30.000000"
}
```

**Error Handling**: If the query fails, the task retries up to 2 times before failing the DAG run.

---

### Task 2: `validate_audience`

**Purpose**: Validate that the audience meets all criteria for campaign execution, including minimum size, data integrity, and anomaly detection.

**Functions Called** (from `dags/helpers.py`):
- `validate_audience_size()` - Checks count >= MIN_AUDIENCE_SIZE
- `validate_audience_anomalies()` - Checks count <= 2x historical average
- `validate_recipient_data()` - Checks required fields (`renter_id`, `phone`)

**Implementation Location**: `dags/sms_reactivation_dag.py`, lines 168-248

**Input** (XCom from Task 1):
- `audience_data`: Dict containing `recipients`, `count`, and `query_timestamp`

**Validation Steps**:

1. **Audience Size Validation** (`validate_audience_size`)
   - Checks: `audience_count >= MIN_AUDIENCE_SIZE` (default: 1)
   - Failure: Returns `is_valid: False` with error message

2. **Recipient Data Validation** (`validate_recipient_data`)
   - Checks: All records have required fields (`renter_id`, `phone`)
   - Failure: Returns `is_valid: False` with missing fields info

3. **Anomaly Detection** (`validate_audience_anomalies`)
   - Checks: `audience_count <= ANOMALY_THRESHOLD_MULTIPLIER * historical_average`
   - Default threshold: 2.0x (10,000 if historical average is 5,000)
   - Failure: Returns `is_valid: False` with anomaly details

**Output** (XCom key: `validation_result`):

| Field | Type | Description |
|-------|------|-------------|
| `is_valid` | `bool` | Whether validation passed |
| `error_message` | `str \| None` | Error description if validation failed |
| `audience_count` | `int` | The validated audience count |
| `audience` | `list[dict]` | The recipient list (passed through for downstream tasks) |

**Example Output (Success)**:
```python
{
    "is_valid": True,
    "error_message": None,
    "audience_count": 5000,
    "audience": [{"renter_id": "ABC123", "phone": "+1234567890"}, ...]
}
```

**Example Output (Failure)**:
```python
{
    "is_valid": False,
    "error_message": "Anomaly detected: audience count 15000 exceeds threshold 10000",
    "audience_count": 15000,
    "audience": [...]
}
```

---

### Task 3: `execute_campaign_send`

**Purpose**: Send the SMS campaign to eligible recipients via the ESP (Email Service Provider).

**Function Called**: 
- `execute_campaign_send()` from `src/pipeline.py`
- Uses `ESPClient` from `src/pipeline.py`

**Implementation Location**: `dags/sms_reactivation_dag.py`, lines 254-321

**Input** (XCom from Task 2):
- `validation_result`: Dict containing `is_valid`, `audience`, `audience_count`

**Process**:
1. Check if validation passed (`is_valid == True`)
2. If validation failed or audience empty, skip campaign and return zero results
3. Initialize `ESPClient`
4. Execute campaign send with retry logic
5. Return campaign results

**Campaign Flow** (`execute_campaign_send` in `src/pipeline.py`):
1. Load existing sent log to deduplicate recipients
2. Split audience into batches of 100 (`BATCH_SIZE`)
3. For each batch:
   - Send to ESP with retry logic (up to 5 retries)
   - Handle rate limiting (429 responses) with exponential backoff
   - Log failures to `failed_batches.json`
4. Save updated sent log to prevent duplicate sends

**Output** (XCom key: `campaign_result`):

| Field | Type | Description |
|-------|------|-------------|
| `total_sent` | `int` | Number of messages successfully sent |
| `total_failed` | `int` | Number of messages that failed |
| `total_skipped` | `int` | Number of recipients skipped (deduplicated) |
| `elapsed_seconds` | `float` | Total execution time in seconds |
| `status` | `str` | `"completed"`, `"skipped"`, or `"failed"` |
| `error_message` | `str \| None` | Error details if status is not `completed` |

**Example Output**:
```python
{
    "total_sent": 4850,
    "total_failed": 50,
    "total_skipped": 100,
    "elapsed_seconds": 125.50,
    "status": "completed",
    "error_message": None
}
```

---

### Task 4: `log_results_and_notify`

**Purpose**: Log campaign results to the BigQuery reporting table and send Slack notification.

**Functions Called** (from `dags/helpers.py`):
- `log_to_reporting_table()` - Logs results to BigQuery reporting table
- `send_slack_success()` - Sends success notification to Slack
- `send_slack_alert()` - Sends failure/alert notification to Slack

**Implementation Location**: `dags/sms_reactivation_dag.py`, lines 327-410

**Input** (XCom from Task 3):
- `campaign_result`: Dict containing campaign execution results

**Process**:
1. Determine campaign status (success = `completed`, failure = `skipped`/`failed`)
2. Log results to BigQuery reporting table (`lifecycle_platform.campaign_results`)
3. Send Slack notification based on status:
   - **Success**: Send summary with sent/failed/skipped counts
   - **Failure**: Send alert with error details

**Reporting Table Schema** (`lifecycle_platform.campaign_results`):

| Column | Type | Description |
|--------|------|-------------|
| `campaign_id` | `STRING` | Unique campaign identifier |
| `execution_date` | `TIMESTAMP` | DAG execution timestamp |
| `audience_count` | `INT64` | Total audience size |
| `sent_count` | `INT64` | Successfully sent messages |
| `failed_count` | `INT64` | Failed messages |
| `skipped_count` | `INT64` | Skipped (deduplicated) messages |
| `duration_seconds` | `FLOAT64` | Total execution time |
| `status` | `STRING` | `completed`, `failed`, or `skipped` |
| `error_message` | `STRING` | Error details if failed |
| `created_at` | `TIMESTAMP` | Record creation timestamp |

**Output** (XCom key: `status`):

| Field | Type | Description |
|-------|------|-------------|
| `reporting_logged` | `bool` | Whether results were successfully logged to BigQuery |
| `notification_sent` | `bool` | Whether Slack notification was sent |

**Example Output**:
```python
{
    "reporting_logged": True,
    "notification_sent": True
}
```

---

## Configuration Constants

### DAG Configuration

| Constant | Value | Description |
|----------|-------|-------------|
| `DAG_ID` | `"sms_reactivation"` | Unique DAG identifier |
| `DAG_DESCRIPTION` | `"Daily SMS reactivation campaign for dormant renters"` | DAG description |
| `SCHEDULE` | `"0 5 * * *"` | Cron schedule (daily at 5:00 AM UTC) |
| `SLA_HOURS` | `3` | SLA in hours (must complete by 8:00 AM UTC) |
| `MAX_RETRIES` | `2` | Number of retry attempts per task |
| `RETRY_DELAY_MINUTES` | `5` | Delay between retries |

### Campaign Configuration

| Constant | Value | Description |
|----------|-------|-------------|
| `CAMPAIGN_ID` | `"sms_reactivation_daily"` | Campaign identifier for ESP |
| `DEFAULT_PROJECT_ID` | `"local-project"` | Default BigQuery project ID |

### Validation Configuration

| Constant | Value | Description |
|----------|-------|-------------|
| `MIN_AUDIENCE_SIZE` | `1` | Minimum eligible recipients required |
| `ANOMALY_THRESHOLD_MULTIPLIER` | `2.0` | Multiplier for anomaly detection (2x) |
| `HISTORICAL_AUDIENCE_AVG` | `5000` | Default historical average for comparison |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LIFECYCLE_PROJECT_ID` | BigQuery project ID (overrides default) |
| `HISTORICAL_AUDIENCE_AVG` | Historical audience average (overrides default) |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications |

### Pipeline Configuration (`src/pipeline.py`)

| Constant | Value | Description |
|----------|-------|-------------|
| `BATCH_SIZE` | `100` | Recipients per batch for ESP |
| `MAX_RETRIES` | `5` | Retry attempts per batch send |
| `BASE_DELAY` | `1.0` | Base delay for exponential backoff (seconds) |
| `MAX_JITTER` | `0.5` | Maximum jitter for backoff (seconds) |

---

## Error Handling

### Task-Level Error Handling

Each task implements specific error handling:

1. **`run_audience_query`**:
   - Catches BigQuery query errors
   - Retries on transient errors (up to 2 times)
   - Logs detailed error information for debugging

2. **`validate_audience`**:
   - Validation failures return `is_valid: False` instead of raising exceptions
   - Allows pipeline to continue to Task 3, which will skip sending
   - Error details propagated through `error_message` field

3. **`execute_campaign_send`**:
   - If validation failed: Returns zero results with `status: "skipped"`
   - If audience empty: Returns zero results with `status: "skipped"`
   - Individual batch failures logged to `failed_batches.json`
   - Overall send continues even if some batches fail

4. **`log_results_and_notify`**:
   - Uses `contextlib.suppress(Exception)` for optional execution date parsing
   - Each operation (reporting log, Slack notification) returns boolean success flag
   - Failures in one operation don't abort the other

### Error Propagation

| Scenario | Behavior |
|----------|----------|
| BigQuery query failure | Task retries → DAG fails if all retries exhausted |
| Validation failure | Success response with `is_valid: False` → Task 3 skips sending |
| ESP send failure | Batch marked as failed → Continues with remaining batches |
| Slack notification failure | Returns `notification_sent: False` → DAG continues |
| Reporting table insert failure | Returns `reporting_logged: False` → DAG continues |

---

## Retry Policy

### Task Retry Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `retries` | `2` | Maximum retry attempts per task |
| `retry_delay` | `5 minutes` | Delay between retry attempts |
| `retry_exponential_backoff` | `False` | Linear retry delay (not exponential) |
| `execution_timeout` | `3 hours` | Maximum execution time per task |

### Retry Behavior

- **Task-Level Retries**: Each task inherits `MAX_RETRIES = 2` and `RETRY_DELAY_MINUTES = 5`
- **Retry Delay**: Configured as `timedelta(minutes=5)` in `default_args`
- **Exponential Backoff**: Disabled at task level; however, the campaign send function (`send_batch_with_retry` in `pipeline.py`) implements exponential backoff internally

### Internal Retry Logic (Pipeline)

The `send_batch_with_retry()` function in `src/pipeline.py` implements its own retry logic:

- **Max Retries**: 5 attempts per batch
- **Backoff Formula**: `delay = base_delay * (2^attempt) + random(0, max_jitter)`
- **Base Delay**: 1.0 second
- **Max Jitter**: 0.5 seconds
- **Rate Limit Handling**: Automatically retries on HTTP 429 (rate limited) responses

---

## Local Development

### Prerequisites

1. **Python 3.12** via mise
2. **Poetry** for dependency management
3. **LocalGCP** (BigQuery emulator) running

### Setup Instructions

```bash
# Install dependencies
pip install -e .

# Start BigQuery emulator
localgcp up

# Setup database (if needed)
python -c "from src.lifecycle_platform.database import setup_database; setup_database()"
```

### Running the DAG Locally

#### Option 1: Airflow Standalone

```bash
# Start Airflow standalone
airflow standalone

# Trigger the DAG manually
airflow dags trigger sms_reactivation
```

#### Option 2: Python Direct Execution

For testing individual functions without full Airflow:

```python
from src.database import get_bigquery_client
from src.repository import AudienceRepository
from src.pipeline import execute_campaign_send, ESPClient
from dags.helpers import (
    validate_audience_size,
    validate_audience_anomalies,
    validate_recipient_data,
    log_to_reporting_table,
)

# 1. Run audience query
client = get_bigquery_client()
repo = AudienceRepository(client)
recipients = repo.get_eligible_recipients()

# 2. Validate audience
is_valid, error = validate_audience_size(len(recipients), min_threshold=1)
is_valid, error = validate_recipient_data(recipients)

# 3. Execute campaign
esp_client = ESPClient()
result = execute_campaign_send("sms_reactivation_daily", recipients, esp_client)

# 4. Log results
log_to_reporting_table(client, "sms_reactivation_daily", len(recipients), ...)
```

#### Option 3: Mock Mode

The DAG includes mock implementations for local development:

- **Slack**: Uses `logger.warning()` instead of actual webhooks when `SLACK_WEBHOOK_URL` is not set
- **ESP Client**: The `ESPClient` class is a stub; implement actual sending logic for production

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_pipeline.py -v
```

### Environment Variables for Local Dev

| Variable | Example Value | Description |
|----------|---------------|-------------|
| `LIFECYCLE_PROJECT_ID` | `local-project` | BigQuery project |
| `HISTORICAL_AUDIENCE_AVG` | `5000` | Expected audience size |
| `SLACK_WEBHOOK_URL` | (optional) | Slack notifications |

### Verification Checklist

- [ ] BigQuery emulator running (`localgcp up`)
- [ ] All dependencies installed (`pip install -e .`)
- [ ] Database schema created
- [ ] Audience query returns results
- [ ] DAG can be triggered via Airflow UI or CLI
- [ ] Logs appear in Airflow task logs

---

## Appendix: Task Dependency Summary

```
run_audience_query (Task 1)
    │
    ├── Output: audience_data {recipients, count, query_timestamp}
    │
    ▼
validate_audience (Task 2)
    │
    ├── Input: audience_data
    ├── Output: validation_result {is_valid, audience_count, audience, error_message}
    │
    ▼
execute_campaign_send (Task 3)
    │
    ├── Input: validation_result
    ├── Output: campaign_result {total_sent, total_failed, total_skipped, elapsed_seconds}
    │
    ▼
log_results_and_notify (Task 4)
    │
    ├── Input: campaign_result
    └── Output: status {reporting_logged, notification_sent}
```