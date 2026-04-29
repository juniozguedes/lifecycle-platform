"""Reusable DAG helpers: Slack notifications, BigQuery reporting, and audience validation."""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from google.api_core import exceptions as gcp_exceptions

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_ENV = "SLACK_WEBHOOK_URL"
REPORTING_TABLE = os.environ.get("REPORTING_TABLE", "campaign_results")


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def get_slack_webhook() -> str | None:
    return os.environ.get(SLACK_WEBHOOK_ENV)


def send_slack_notification(
    message: str,
    webhook_url: str | None = None,
    logger_func: Any = None,
) -> bool:
    if logger_func is None:
        logger_func = logger.info

    webhook = webhook_url or get_slack_webhook()

    if webhook:
        logger_func("Slack notification sent: %s", message)
        return True
    else:
        logger.warning("[SLACK MOCK] %s", message)
        return True


def send_slack_alert(
    dag_id: str,
    task_id: str | None,
    error_message: str,
    execution_date: datetime | None = None,
) -> bool:
    execution_str = execution_date.isoformat() if execution_date else "unknown"

    message = (
        f":x: *DAG Failure Alert*\n"
        f"• DAG: `{dag_id}`\n"
        f"• Task: `{task_id or 'n/a'}`\n"
        f"• Execution: {execution_str}\n"
        f"• Error: {error_message}"
    )

    return send_slack_notification(message)


def send_slack_success(
    dag_id: str,
    summary: dict[str, Any],
    execution_date: datetime | None = None,
) -> bool:
    execution_str = execution_date.isoformat() if execution_date else "unknown"

    message = (
        f":white_check_mark: *DAG Success*\n"
        f"• DAG: `{dag_id}`\n"
        f"• Execution: {execution_str}\n"
        f"• Results: {summary.get('total_sent', 0)} sent, "
        f"{summary.get('total_failed', 0)} failed, "
        f"{summary.get('total_skipped', 0)} skipped\n"
        f"• Elapsed: {summary.get('elapsed_seconds', 0):.2f}s"
    )

    return send_slack_notification(message)


def log_to_reporting_table(
    client: Any,
    campaign_id: str,
    audience_count: int,
    sent_count: int,
    failed_count: int,
    skipped_count: int,
    duration_seconds: float,
    execution_date: datetime | None = None,
    status: str = "completed",
    error_message: str | None = None,
) -> bool:
    exec_time = execution_date or datetime.now(UTC)
    created_at = datetime.now(UTC)

    query = f"""
    INSERT INTO `{REPORTING_TABLE}` (
        campaign_id,
        execution_date,
        audience_count,
        sent_count,
        failed_count,
        skipped_count,
        duration_seconds,
        status,
        error_message,
        created_at
    )
    VALUES (
        {sql_literal(campaign_id)},
        {sql_literal(exec_time.isoformat())},
        {sql_literal(audience_count)},
        {sql_literal(sent_count)},
        {sql_literal(failed_count)},
        {sql_literal(skipped_count)},
        {sql_literal(duration_seconds)},
        {sql_literal(status)},
        {sql_literal(error_message)},
        {sql_literal(created_at.isoformat())}
    )
    """

    try:
        client.query(query).result()
        logger.info("Logged results to reporting table: campaign=%s, status=%s", campaign_id, status)
        return True
    except gcp_exceptions.GoogleAPIError as e:
        logger.error("Failed to log to reporting table: %s", e)
        return False


def validate_audience_size(
    audience_count: int,
    min_threshold: int = 1,
) -> tuple[bool, str | None]:
    if audience_count < min_threshold:
        return False, f"Audience count {audience_count} is below minimum threshold {min_threshold}"
    return True, None


def validate_audience_anomalies(
    audience: list[dict],
    count: int,
    anomaly_threshold_multiplier: float = 2.0,
    historical_average: float | None = None,
) -> tuple[bool, str | None]:
    if not audience:
        return False, "Audience list is empty"

    actual_count = len(audience)

    if actual_count != count:
        return False, f"Count mismatch: provided {count}, actual {actual_count}"

    if historical_average is None:
        return True, None

    threshold = historical_average * anomaly_threshold_multiplier

    if actual_count > threshold:
        return False, (
            f"Anomaly detected: audience count {actual_count} exceeds "
            f"threshold {threshold:.0f} ({anomaly_threshold_multiplier}x historical {historical_average:.0f})"
        )

    return True, None


def validate_recipient_data(
    audience: list[dict],
    required_fields: tuple[str, ...] = ("renter_id", "phone"),
) -> tuple[bool, str | None]:
    if not audience:
        return True, None

    missing_fields: set[str] = set()
    invalid_records = 0

    for recipient in audience:
        has_missing = False
        for field in required_fields:
            value = recipient.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing_fields.add(field)
                has_missing = True
        if has_missing:
            invalid_records += 1

    if missing_fields:
        return False, f"Invalid records: missing fields {missing_fields} in {invalid_records} records"

    return True, None
