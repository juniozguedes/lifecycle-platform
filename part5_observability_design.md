# Part 5 — Observability Design

This document describes the metrics, alerts, double-send protections, and ESP failure handling I would add for the SMS reactivation pipeline.

## 1. Datadog Metrics and Alerts

We can improve the pipeline observability at three levels: Airflow orchestration, audience quality, and ESP delivery.

For Airflow, we can emit or track:

- `sms_reactivation.dag.duration_seconds`
- `sms_reactivation.dag.success`
- `sms_reactivation.dag.failure`
- `sms_reactivation.task.duration_seconds` tagged by `task_id`
- `sms_reactivation.task.retries` tagged by `task_id`
- `sms_reactivation.sla_miss`

Alerts:

- DAG has not completed by 8:00 AM UTC.
- Any task fails after retries.
- Runtime is more than 2x the 7-day average.
- `run_audience_query` or `execute_campaign_send` retries more than once in a run.

For audience quality, I would track:

- `sms_reactivation.audience.count`
- `sms_reactivation.audience.valid`
- `sms_reactivation.audience.validation_failure`
- `sms_reactivation.audience.suppressed_count`
- `sms_reactivation.audience.model_filtered_count` if model scores are enabled
- `sms_reactivation.audience.model_missing_count`

Alerts:

- Audience count is `0`.
- Audience count is greater than `2x` historical average.
- Audience count drops more than 50% from the 7-day average.
- Model score freshness check fails or model-filtered audience is unexpectedly empty.

For ESP delivery, I would track:

- `sms_reactivation.esp.sent`
- `sms_reactivation.esp.failed`
- `sms_reactivation.esp.skipped_deduped`
- `sms_reactivation.esp.batch.success`
- `sms_reactivation.esp.batch.failure`
- `sms_reactivation.esp.rate_limited`
- `sms_reactivation.esp.retry_count`
- `sms_reactivation.esp.latency_ms`

Alerts:

- ESP failure rate above 5% for a run.
- Any batch receives repeated `429` responses after retries.
- Total failed recipients above a fixed threshold, such as 100.
- Send completion rate below 95%.

Every metric should be tagged with:

```text
campaign_id:sms_reactivation_daily
dag_id:sms_reactivation
environment:local|staging|prod
model_version:<version if applicable>
```

This makes it easy to compare campaign runs and debug whether failures are isolated to orchestration, data, or ESP delivery.

## 2. Detecting and Preventing Double-Sends

The current implementation uses a file-based sent log (`sent_renters.json`) to prevent sending the same `renter_id` twice for the same campaign. That satisfies the POC requirement for a simple local approach.

For production, we would move this from a file to a durable BigQuery table:

```sql
CREATE TABLE lifecycle_platform.campaign_send_log (
    campaign_id STRING,
    renter_id STRING,
    execution_date DATE,
    sent_at TIMESTAMP,
    esp_message_id STRING,
    status STRING
);
```

Before sending, the pipeline should anti-join the audience against this send log:

```sql
WHERE NOT EXISTS (
    SELECT 1
    FROM lifecycle_platform.campaign_send_log l
    WHERE l.campaign_id = @campaign_id
      AND l.renter_id = audience.renter_id
      AND l.status IN ('sent', 'accepted')
)
```

The send operation should also be idempotent at the ESP boundary. Each recipient should include an idempotency key like:

```text
sms_reactivation_daily:<renter_id>:<campaign_date>
```

That protects against:

- Airflow task retries after a partial send.
- Manual DAG re-triggers.
- Process crashes after the ESP accepted a batch but before local state was fully written.

Detection:

- Alert if the same `(campaign_id, renter_id, execution_date)` appears more than once in the send log.
- Track `sms_reactivation.esp.skipped_deduped` so reruns are visible.
- Reconcile ESP accepted message IDs back to the send log.

The important principle is to mark a renter as sent only after the ESP accepts the batch. For partial failures, successful recipients should be recorded and failed recipients should remain retryable.

## 3. ESP Outage and Circuit Breaker Strategy

If the ESP goes down mid-send, the pipeline should not fail the entire campaign on the first bad batch. It should retry each failed batch with exponential backoff and jitter, which the current implementation already does for `429` and network-style errors.

After repeated failures, the pipeline should open a circuit breaker:

- Stop sending new batches for that run.
- Write unsent/failed batches to a retryable failure log.
- Alert Slack with actionable context.
- Mark the DAG run as degraded or failed depending on how much of the audience was affected.

Example alert:

```text
SMS Reactivation degraded: ESP unavailable.
Campaign: sms_reactivation_daily
Sent: 1,200
Failed/unsent: 400
Reason: repeated 429/timeouts after 5 retries
Recovery: failed batches written to failed_batches.json / campaign_send_failures table
```

For production, I would store failed batches in a durable table:

```sql
CREATE TABLE lifecycle_platform.campaign_send_failures (
    campaign_id STRING,
    execution_date DATE,
    batch_id STRING,
    renter_ids ARRAY<STRING>,
    error_type STRING,
    error_message STRING,
    retry_count INT64,
    created_at TIMESTAMP,
    resolved_at TIMESTAMP
);
```

Recovery strategy:

1. If the ESP recovers quickly, re-run only failed batches.
2. If outage lasts past the campaign window, pause the campaign and notify Lifecycle.
3. Do not resend successful recipients; use the send log/idempotency key to skip them.
4. Add a manual replay command or DAG task that reads only unresolved failed batches.

This avoids both failure modes: blasting duplicate messages to users and silently dropping a large part of the audience.

## Summary

The observability design should make four things obvious: whether the DAG ran on time, whether the audience was sane, whether ESP delivery was healthy, and whether duplicate sends were prevented. The recovery strategy should be conservative: retry transient failures, stop when the ESP is clearly unhealthy, persist failed batches, and make replay idempotent.
