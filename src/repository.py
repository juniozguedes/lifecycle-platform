from pathlib import Path

from google.cloud import bigquery

from src.database import get_bigquery_client, load_sql_file

QUERY_FILE = Path(__file__).parent / "sql" / "audience_query.sql"
STAGING_TABLE = "sms_reactivation_audience_staging"


class AudienceRepository:
    """Repository for audience/campaign data access."""

    def __init__(self, client: bigquery.Client):
        self._client = client

    def get_eligible_recipients(self) -> list[dict]:
        """Returns all recipients eligible for campaign sends."""
        statements = load_sql_file(QUERY_FILE)
        if not statements:
            raise ValueError(f"No SQL statements found in {QUERY_FILE}")
        results = self._client.query(statements[0]).result()
        return [dict(row) for row in results]

    def export_eligible_recipients_to_staging(self, staging_table: str = STAGING_TABLE) -> int:
        """Materializes eligible campaign recipients into a staging table."""
        statements = load_sql_file(QUERY_FILE)
        if not statements:
            raise ValueError(f"No SQL statements found in {QUERY_FILE}")

        audience_query = statements[0]
        self._client.query(f"CREATE OR REPLACE TABLE `{staging_table}` AS {audience_query}").result()
        count_rows = list(self._client.query(f"SELECT COUNT(*) AS cnt FROM `{staging_table}`").result())
        return count_rows[0].cnt if count_rows else 0

    def get_staged_recipients(self, staging_table: str = STAGING_TABLE) -> list[dict]:
        """Returns recipients from the staging table created for this campaign run."""
        query = f"""
        SELECT renter_id, email, phone, last_login, search_count, days_since_login
        FROM `{staging_table}`
        ORDER BY days_since_login DESC
        """
        results = self._client.query(query).result()
        return [dict(row) for row in results]


def run_audience_query(client: bigquery.Client | None = None) -> list[dict]:
    """Convenience wrapper for backward compatibility."""

    if client is None:
        client = get_bigquery_client()
    return AudienceRepository(client).get_eligible_recipients()
