from pathlib import Path

from google.cloud import bigquery

from .database import get_bigquery_client, load_sql_file

QUERY_FILE = Path(__file__).parent.parent.parent / "sql" / "audience_query.sql"


class AudienceRepository:
    """Repository for audience/campaign data access."""

    def __init__(self, client: bigquery.Client):
        self._client = client

    def get_eligible_recipients(self) -> list[dict]:
        """Returns all recipients eligible for campaign sends."""
        query = load_sql_file(QUERY_FILE)[0]
        results = self._client.query(query).result()
        return [dict(row) for row in results]


def run_audience_query(client: bigquery.Client | None = None) -> list[dict]:
    """Convenience wrapper for backward compatibility."""

    if client is None:
        client = get_bigquery_client()
    return AudienceRepository(client).get_eligible_recipients()
