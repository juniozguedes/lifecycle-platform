import os
from pathlib import Path
from typing import Optional
from google.cloud import bigquery
from google.auth import credentials
import argparse


SCHEMA_FILE = Path(__file__).parent.parent.parent / "sql" / "schema.sql"
SEED_FILE = Path(__file__).parent.parent.parent / "sql" / "seed_data.sql"
QUERY_FILE = Path(__file__).parent.parent.parent / "sql" / "audience_query.sql"


def get_bigquery_client(project_id: str = "local-project") -> bigquery.Client:
    endpoint = os.environ.get("CLOUDSDK_API_ENDPOINT_OVERRIDES_BIGQUERY", "http://localhost:9060")
    return bigquery.Client(
        project=project_id,
        credentials=credentials.AnonymousCredentials(),
        client_options={"api_endpoint": endpoint},
    )


def load_sql_file(file_path: Path) -> list[str]:
    content = file_path.read_text()
    statements = [s.strip() for s in content.split(";") if s.strip()]
    return statements


def initialize_schema(client: bigquery.Client) -> None:
    """Creates all database tables. Run once on initial setup."""
    statements = load_sql_file(SCHEMA_FILE)
    for stmt in statements:
        client.query(stmt).result()


def load_seed_data(client: bigquery.Client) -> None:
    """Loads demo/test data. Only for development, NOT automatic."""
    statements = load_sql_file(SEED_FILE)
    for stmt in statements:
        client.query(stmt).result()


def run_audience_query(client: bigquery.Client) -> list[dict]:
    """Executes the audience query for production campaigns."""
    query = load_sql_file(QUERY_FILE)[0]
    results = client.query(query).result()
    return [dict(row) for row in results]


def setup_for_development(client: bigquery.Client) -> None:
    """Dev only: create schema + load seed data."""
    initialize_schema(client)
    load_seed_data(client)


def setup_database(client: Optional[bigquery.Client] = None) -> bigquery.Client:
    """Deprecated: Use initialize_schema() for production or setup_for_development() for dev."""
    if client is None:
        client = get_bigquery_client()
    initialize_schema(client)
    load_seed_data(client)
    return client


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lifecycle Platform Database Setup")
    parser.add_argument(
        "--mode",
        choices=["production", "development"],
        default="production",
        help="production: schema only (safe for prod). development: schema + seed data",
    )
    args = parser.parse_args()

    client = get_bigquery_client()

    if args.mode == "development":
        print("Setting up database for development...")
        setup_for_development(client)
    else:
        print("Setting up schema for production...")
        initialize_schema(client)

    print("Running audience query...")
    results = run_audience_query(client)
    print(f"Found {len(results)} recipients:")
    for r in results:
        print(f"  - {r['renter_id']}: {r['phone']} ({r['search_count']} searches, {r['days_since_login']} days ago)")