# Lifecycle Platform

## Setup

### Prerequisites

- Python 3.12+
- LocalGCP (for local BigQuery emulation): https://localgcp.com/

```bash
# Install LocalGCP
brew install slokam-ai/tap/localgcp

# Start BigQuery emulator (in separate terminal)
localgcp up

# Install Python dependencies
pip install -e .
```

### Database Setup

Automatically creates tables and loads sample data:

```python
from src.lifecycle_platform.database import setup_database, run_audience_query

# Setup (creates schema + seed data)
client = setup_database()

# Run the audience query
results = run_audience_query(client)
```

## Run Tests

```bash
pytest tests/
```

## Project Structure

```
.
├── sql/
│   ├── schema.sql          # Table definitions
│   ├── seed_data.sql      # Sample test data
│   └── audience_query.sql # Part 1 solution
├── src/
│   └── lifecycle_platform/
│       └── database.py    # Python query helpers
├── tests/
│   └── test_*.py
├── ai-session/
│   └── claude-log.md    # AI usage log
└── pyproject.toml
```

## Assumptions

- LocalGCP runs on localhost:9060 (default)
- BigQuery emulator uses in-memory storage (data resets on restart)
- Sample data represents typical edge cases

## Design Decisions

1. **LEFT JOIN + GROUP BY** - Efficient for counting searches per renter
2. **NOT EXISTS** - Cleaner than LEFT JOIN + IS NULL for suppression exclusion

## Next Steps

- Part 2: Pipeline orchestration (Python batch sending)
- Part 3: Airflow DAG skeleton
- Part 4: Value model integration (ML JOIN)
- Part 5: Observability design