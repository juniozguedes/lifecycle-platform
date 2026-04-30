# Part 4 — Value Model Integration

This document describes how I would extend the SMS reactivation pipeline to use the daily renter conversion score table:

```sql
ml_predictions.renter_send_scores
```

The goal is to send only to renters whose `predicted_conversion_probability` is above a configurable threshold, while keeping the design flexible enough to support additional models and segments later.

## 1. BigQuery Query Changes

The current audience query should join eligible renters to the latest model scores for the same run date. The threshold should not be hardcoded in SQL; it should come from configuration, such as an Airflow Variable, a YAML config, or a BigQuery campaign configuration table.

Example pattern:

```sql
WITH latest_scores AS (
    SELECT
        renter_id,
        predicted_conversion_probability,
        model_version,
        scored_at
    FROM ml_predictions.renter_send_scores
    WHERE DATE(scored_at) = CURRENT_DATE()
),
base_audience AS (
    -- Existing Part 1 audience query logic:
    -- churned renters, >30 days since login, >=3 searches,
    -- phone present, sms_consent = TRUE, not suppressed, DND expired.
)
SELECT
    a.renter_id,
    a.email,
    a.phone,
    a.last_login,
    a.search_count,
    a.days_since_login,
    s.predicted_conversion_probability,
    s.model_version
FROM base_audience a
JOIN latest_scores s
    ON s.renter_id = a.renter_id
WHERE s.predicted_conversion_probability >= @conversion_threshold;
```

For the first campaign, `@conversion_threshold` could default to `0.30`. For future campaigns or segments, I would move this into a config table:

```sql
CREATE TABLE lifecycle_platform.campaign_model_config (
    campaign_id STRING,
    segment_name STRING,
    model_table STRING,
    model_version STRING,
    threshold FLOAT64,
    is_active BOOLEAN
);
```

That lets us support multiple models without rewriting the DAG. The DAG reads the campaign config, injects the relevant threshold/table/version, and executes the same audience-building pattern.

## 2. Airflow DAG Dependency on Fresh Scores

Before running the audience query, the DAG should confirm that model scores are fresh for the campaign date.

I would add a task before `run_audience_query`:

```text
wait_for_model_scores -> run_audience_query -> validate_audience -> execute_campaign_send -> log_results_and_notify
```

Implementation options:

- Use a `BigQueryCheckOperator` or custom `@task` that checks:
  ```sql
  SELECT COUNT(*) > 0
  FROM ml_predictions.renter_send_scores
  WHERE DATE(scored_at) = CURRENT_DATE()
  ```
- If the model scoring DAG is also in Airflow, use `ExternalTaskSensor` to wait for that DAG/task to succeed.
- Store the expected `model_version` in campaign config and check that today’s scores exist for that version.

The custom task approach is simple and explicit:

```python
@task(task_id="wait_for_model_scores")
def wait_for_model_scores() -> dict:
    threshold = float(Variable.get("sms_reactivation_model_threshold", 0.30))
    client = get_bigquery_client(get_project_id())
    rows = list(client.query("""
        SELECT COUNT(*) AS score_count
        FROM ml_predictions.renter_send_scores
        WHERE DATE(scored_at) = CURRENT_DATE()
    """).result())

    score_count = rows[0].score_count if rows else 0
    if score_count == 0:
        raise ValueError("Model scores are not fresh for today's campaign run")

    return {"score_count": score_count, "threshold": threshold}
```

For production, I would prefer a deferrable sensor or a short-poke sensor so the scheduler does not waste worker capacity while waiting.

## 3. Handling Model Delays

If model scoring has not completed by the 5:00 AM campaign start, I would not immediately fail the campaign. The business tradeoff is nuanced:

- Sending without scores wastes SMS volume and may hurt user experience.
- Skipping entirely can lose revenue from high-intent renters.

Recommended policy:

1. Wait for scores until a defined cutoff, such as 7:30 AM UTC.
2. If scores arrive before the cutoff, run normally.
3. If scores are still missing at cutoff:
   - For normal campaigns: skip the send and alert lifecycle/DS teams.
   - For high-priority campaigns: optionally fall back to the non-modeled audience with a stricter cap, but only if approved by business owners.

I would make the fallback behavior configurable per campaign:

```yaml
campaign_id: sms_reactivation_daily
model_threshold: 0.30
model_freshness_cutoff_utc: "07:30"
on_model_missing: "skip"  # allowed: skip, fallback_capped, fail
fallback_max_audience: 1000
```

For this POC, I would choose `skip` as the safest default because the prompt explicitly says model scores reduce wasted volume. The DAG should send a Slack alert like:

```text
SMS Reactivation skipped: model scores missing for 2026-04-29 by 07:30 UTC.
No renters were sent. Data Science and Lifecycle notified.
```

## 4. Future-Proofing for Multiple Models

Since another model is expected in six weeks, the key design decision is to avoid hardcoding model table names and thresholds inside the DAG.

I would introduce a small configuration layer:

- `campaign_id`
- `segment_name`
- `model_table`
- `threshold`
- `freshness_field`
- `freshness_policy`
- `fallback_policy`

Then the pipeline can support:

- SMS reactivation model with threshold `0.30`
- Winback model with threshold `0.45`
- New-user lifecycle model with threshold `0.20`

All without changing the orchestration shape. We only update configuration and the audience query template.

## Summary

The model should be treated as a configurable eligibility filter layered on top of the deterministic audience rules. Airflow should verify score freshness before sending, wait up to a business-approved cutoff, then skip or fallback based on campaign policy. This preserves send quality today and keeps the design ready for multiple segments and models later.
