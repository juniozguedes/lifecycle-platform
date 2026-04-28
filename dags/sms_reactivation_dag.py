"""SMS Reactivation DAG for the lifecycle platform."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from airflow import DAG
from airflow.decorators import task
from airflow.models.variable import Variable
from airflow.operators.python import get_current_context

from helpers import (
    log_to_reporting_table,
    send_slack_alert,
    send_slack_success,
    validate_audience_anomalies,
    validate_audience_size,
    validate_recipient_data,
)
from src.database import get_bigquery_client, initialize_schema, load_seed_data
from src.pipeline import ESPClient, execute_campaign_send
from src.repository import AudienceRepository

logger = logging.getLogger(__name__)

DAG_ID = "sms_reactivation"
CAMPAIGN_ID = "sms_reactivation_daily"
DEFAULT_PROJECT_ID = "local-project"
MIN_AUDIENCE_SIZE = 1
ANOMALY_THRESHOLD_MULTIPLIER = 2.0
HISTORICAL_AUDIENCE_AVG = 5000

default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": False,
    "execution_timeout": timedelta(hours=3),
    "sla": timedelta(hours=3),
}


def get_project_id() -> str:
    return Variable.get("lifecycle_project_id", DEFAULT_PROJECT_ID)


def get_historical_average() -> float:
    try:
        return float(Variable.get("historical_audience_avg", HISTORICAL_AUDIENCE_AVG))
    except (TypeError, ValueError):
        return float(HISTORICAL_AUDIENCE_AVG)


with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Daily SMS reactivation campaign for dormant renters",
    schedule="0 5 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
) as dag:

    @task(task_id="database_provisioning")
    def database_provisioning() -> dict[str, Any]:
        """Step 0: Ensure database infrastructure is ready before campaign runs.

        Checks if required BigQuery tables exist and have data.
        - If tables don't exist: create schema
        - If tables exist but empty: load seed data
        - If tables have data: skip (idempotent)
        """
        project_id = get_project_id()
        logger.info("Starting database provisioning for project: %s", project_id)
        client = get_bigquery_client(project_id)

        required_tables = [
            ("", "renter_activity"),
            ("", "renter_profiles"),
            ("", "suppression_list"),
            ("ml_predictions", "renter_send_scores"),
        ]

        tables_exist = True
        all_tables_have_data = True

        for dataset_id, table_name in required_tables:
            # Determine the dataset to use
            dataset_name = dataset_id.strip() if dataset_id.strip() else "lifecycle_platform"
            full_table_name = f"{dataset_name}.{table_name}"

            try:
                table_ref = client.dataset(dataset_name).table(table_name)
                table = client.get_table(table_ref)
                # Table exists, check if it has data
                if table.num_rows == 0:
                    logger.info("Table %s exists but is empty", full_table_name)
                    all_tables_have_data = False
                else:
                    logger.info("Table %s exists with %d rows", full_table_name, table.num_rows)
            except Exception as e:
                # Table doesn't exist
                logger.info("Table %s not found: %s", full_table_name, str(e))
                tables_exist = False
                all_tables_have_data = False

        tables_created = False
        seed_data_loaded = False

        if not tables_exist:
            logger.info("Creating database schema...")
            initialize_schema(client)
            tables_created = True
            logger.info("Schema created successfully")
            # After creating schema, load seed data
            logger.info("Loading seed data...")
            load_seed_data(client)
            seed_data_loaded = True
            logger.info("Seed data loaded successfully")
        elif not all_tables_have_data:
            logger.info("Tables exist but some are empty, loading seed data...")
            load_seed_data(client)
            seed_data_loaded = True
            logger.info("Seed data loaded successfully")
        else:
            logger.info("All tables exist with data, provisioning complete (skipped)")

        return {
            "status": "completed",
            "tables_created": tables_created,
            "seed_data_loaded": seed_data_loaded,
            "provisioning_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @task(task_id="run_audience_query")
    def run_audience_query() -> dict[str, Any]:
        project_id = get_project_id()
        logger.info("Starting audience query for project: %s", project_id)
        client = get_bigquery_client(project_id)
        repository = AudienceRepository(client)
        recipients = repository.get_eligible_recipients()
        count = len(recipients)
        logger.info("Audience query complete: %d eligible recipients found", count)
        return {
            "recipients": recipients,
            "count": count,
            "query_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @task(task_id="validate_audience")
    def validate_audience(audience_data: dict[str, Any]) -> dict[str, Any]:
        recipients = audience_data.get("recipients", [])
        count = audience_data.get("count", 0)
        logger.info("Validating audience: count=%d", count)
        is_valid, error_msg = validate_audience_size(count, MIN_AUDIENCE_SIZE)
        if not is_valid:
            return {"is_valid": False, "error_message": error_msg, "audience_count": count, "audience": []}
        is_valid, error_msg = validate_recipient_data(recipients)
        if not is_valid:
            return {"is_valid": False, "error_message": error_msg, "audience_count": count, "audience": []}
        historical_avg = get_historical_average()
        is_valid, error_msg = validate_audience_anomalies(
            recipients, count, ANOMALY_THRESHOLD_MULTIPLIER, historical_avg
        )
        if not is_valid:
            return {"is_valid": False, "error_message": error_msg, "audience_count": count, "audience": []}
        logger.info("Audience validation passed: count=%d, historical_avg=%.0f", count, historical_avg)
        return {"is_valid": True, "error_message": None, "audience_count": count, "audience": recipients}

    @task(task_id="execute_campaign_send")
    def execute_campaign_send_task(validation_data: dict[str, Any]) -> dict[str, Any]:
        is_valid = validation_data.get("is_valid", False)
        if not is_valid:
            error_msg = validation_data.get("error_message", "Validation failed")
            return {
                "total_sent": 0,
                "total_failed": 0,
                "total_skipped": 0,
                "elapsed_seconds": 0.0,
                "status": "skipped",
                "error_message": error_msg,
                "audience_count": 0,
            }
        recipients = validation_data.get("audience", [])
        if not recipients:
            return {
                "total_sent": 0,
                "total_failed": 0,
                "total_skipped": 0,
                "elapsed_seconds": 0.0,
                "status": "skipped",
                "error_message": "empty_audience",
                "audience_count": 0,
            }
        logger.info("Starting campaign send: campaign_id=%s, recipients=%d", CAMPAIGN_ID, len(recipients))
        esp_client = ESPClient()
        result = execute_campaign_send(campaign_id=CAMPAIGN_ID, audience=recipients, esp_client=esp_client)
        result["status"] = "completed"
        result["error_message"] = None
        result["audience_count"] = len(recipients)
        logger.info("Campaign send complete: sent=%d, failed=%d", result["total_sent"], result["total_failed"])
        return result

    @task(task_id="log_results_and_notify")
    def log_results_and_notify(campaign_data: dict[str, Any]) -> dict[str, bool]:
        project_id = get_project_id()
        client = get_bigquery_client(project_id)
        ctx = get_current_context()
        exec_date: datetime | None = ctx.get("data_interval_start")
        status = campaign_data.get("status", "unknown")
        is_success = status == "completed"
        reporting_logged = log_to_reporting_table(
            client=client,
            campaign_id=CAMPAIGN_ID,
            audience_count=campaign_data.get("audience_count", 0),
            sent_count=campaign_data.get("total_sent", 0),
            failed_count=campaign_data.get("total_failed", 0),
            skipped_count=campaign_data.get("total_skipped", 0),
            duration_seconds=campaign_data.get("elapsed_seconds", 0.0),
            status=status,
            error_message=campaign_data.get("error_message"),
            execution_date=exec_date,
        )
        if is_success:
            notification_sent = send_slack_success(dag_id=DAG_ID, summary=campaign_data, execution_date=exec_date)
        else:
            notification_sent = send_slack_alert(
                dag_id=DAG_ID,
                task_id=None,
                error_message=campaign_data.get("error_message", "Unknown error"),
                execution_date=exec_date,
            )
        return {"reporting_logged": reporting_logged, "notification_sent": notification_sent}

    provisioning_result = database_provisioning()
    audience_result = run_audience_query()
    validation_result = validate_audience(audience_result)
    campaign_result = execute_campaign_send_task(validation_result)
    log_results_and_notify(campaign_result)

    # Set task dependencies: provisioning must complete before audience query
    provisioning_result >> audience_result
