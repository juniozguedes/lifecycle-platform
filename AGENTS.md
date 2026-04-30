# Global Coding Standards

## Git Rules

### MANDATORY: NEVER commit or push unless the user EXPLICITLY uses the words "commit and push the code" ###

### IMPORTANT RULES:
- NEVER commit directly to main - always use dev branch
- If dev branch does not exist, CREATE it first, then push to dev
- Default branch for commits, pushes, and PRs is: dev unless user is working on another branch
- If a PR already exists for the branch, UPDATE the existing PR description instead of creating new PR

- **IMPORTANT**: Check PR status BEFORE editing - if merged, find and update the open PR
- Agent is responsible for creating PRs (no PULL_REQUEST.md files)

### After every explicit "commit and push the code" request:
0. Run the skill `pr-reviewer/` and make sure that the code passes the review
1. Verify code is correct (run project's lint/typecheck/tests if they exist)
2. Update AGENTS.md only if new architecture is added
3. Commit by categories (feat, fix, refactor, docs, etc.)
4. Push to dev branch
5. Create or update PR from dev to main with description

### After each prompt (REQUIRED)
- Check for repeated/dead code/logic in the modified files

### DRY Principle (Don't Repeat Yourself)
- **MANDATORY**: Before writing any function or helper, check if it already exists in the codebase
- **Search first**: Use grep/glob to find existing implementations before creating new ones
- **Shared utilities**: If the same logic is needed in multiple modules, extract to a shared module and import
- **Examples**:
  - `load_sql_file()` used in both `database.py` and `repository.py` → extract to one place, import from there
  - SQL file paths defined multiple times → define once in a config/constants module
  - Same validation logic in multiple endpoints → extract to middleware or decorator
- **Anti-pattern**: Copy-pasting code between files with minor changes
- **Refactor first**: If I find myself writing similar code, stop and refactor to share the logic

## Development Conventions

### Imports
- Imports must always be at the top of the file
- Use absolute imports when possible
- Group: standard library → external → local

### Error Handling
- Avoid broad `catch-all` exceptions
- Be specific about which exceptions are expected
- Use context managers for resources (files, connections)

### Comments
- Do NOT add comments that restate what the code says
- Only explain non-obvious intent, trade-offs, or constraints
- **NEVER add file header docstrings** explaining what the file is about (e.g., "This module handles database operations")

## Lifecycle Platform

### Tech Stack
- **Python 3.12** via mise
- **BigQuery** (with LocalGCP emulator for local dev)
- **Poetry** for dependency management
- **pytest** for testing

### Architecture
- `sql/` — SQL schemas, seed data, and queries
- `src/` — Python modules (`database.py`, `repository.py`, `pipeline.py`)
- `dags/` — Airflow DAG and helper modules
- `tests/` — pytest unit tests
- `skills/` — AI agent skill definitions

### Local Development

```bash
# Start BigQuery emulator
localgcp up

# Install dependencies
pip install -e .

# Run tests
pytest tests/

# Start Airflow; database_provisioning creates schema and local seed data if empty
docker-compose up -d
```

### Airflow Import Style

Keep DAG parse-time imports lightweight. Standard library, Airflow, and local DAG helpers may be imported at module scope, but heavier project modules that load BigQuery/google client code should be imported inside task functions. This keeps DagBag parsing fast and avoids Airflow import timeouts.

### Skills

AI agent skills available in this project:

| Skill | Description |
|-------|-------------|
| `skills/pr-reviewer/` | Code review before push |
| `skills/unit-test/` | Unit test generation |

To invoke a skill, use the `skill` tool in OpenCode.

### Airflow Import Style

- `renter_activity` — User events (page_view, search, etc.)
- `renter_profiles` — User profile data with consent flags
- `suppression_list` — Excluded users
- `ml_predictions.renter_send_scores` — ML model predictions
