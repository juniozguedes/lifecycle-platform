---
name: unit-test
description: Generate focused unit tests for new or changed code, following project conventions and pytest best practices.
---

# Unit Test Generator -- Instructions

> **Prerequisites**: Read `AGENTS.md` in the repository root for testing conventions and coding style.

When the user invokes this skill, generate unit tests for the specified code. If no specific code is mentioned, look at the current git diff to identify changed files that need tests.

## Agent Behavior Rules

- Generate tests in `tests/`, mirroring the `app/` directory structure
- **Before creating any fixture**, search for an existing `conftest.py` up the directory tree (same dir, parent dir, grandparent). Reuse existing fixtures instead of duplicating them
- If no `conftest.py` exists in the target directory and you need a fixture shared by 2+ test files, create one
- Do not modify production code unless asked
- Run `mise test -- <test_file>` after generating tests to verify they pass
- Run `mise lint-fix` to auto-fix formatting

## Step 1: Identify What to Test

Determine the target code:

1. If the user specifies a file or function, use that
2. Otherwise, run `git diff main...HEAD --name-only` to find changed production files
3. Filter to files under `app/` (skip tests, configs, docs)

For each target file, read it and identify:
- Public functions and classes (skip private helpers unless they contain complex logic)
- Input/output contracts (parameters, return types, exceptions)
- System boundary interactions (database queries, HTTP calls, file I/O)
- Edge cases (empty inputs, missing keys, invalid formats)

## Step 2: Generate Tests

### Style Rules

- **pytest-style only**. Never use `unittest.TestCase`
- **No emojis** in test code or comments
- **No numbered step comments** (e.g. `# Step 1: setup`)
- Use type annotations on fixtures and test parameters
- Keep tests focused: one behavior per test function
- **Use `pathlib.Path` for file operations** -- when using pytest's `tmp_path` fixture, annotate as `tmp_path: Path` (not `str`). Use pathlib operators (`tmp_path / "file.txt"`, `.write_text()`, `.read_text()`, `.mkdir()`, `.is_file()`, `.name`, `.iterdir()`) instead of `os.path.join`, `os.makedirs`, `os.path.isfile`, or manual `open()` read/write helpers

### Test Structure

```python
"""Tests for <module_path>."""

import pytest
from unittest.mock import MagicMock, patch

from app.<path> import <target>


class TestTargetFunction:
    """Tests for target_function."""

    def test_happy_path(self) -> None:
        result = target_function(valid_input)
        assert result == expected

    def test_edge_case(self) -> None:
        result = target_function(empty_input)
        assert result == []

    def test_raises_on_invalid_input(self) -> None:
        with pytest.raises(ValueError, match="expected message"):
            target_function(bad_input)
```

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<FunctionOrClassName>`
- Test functions: `test_<behavior_description>` -- describe what happens, not the method name
  - Good: `test_returns_empty_list_when_no_slots_available`
  - Bad: `test_get_available_slots`

### Fixtures

- Use `conftest.py` for fixtures shared across multiple test files in the same directory
- Use inline fixtures (in the test file) for fixtures used only in that file
- Fixtures should build realistic objects, not empty mocks

#### conftest.py Guidance

When creating tests for services or repositories, create shared fixtures in the appropriate `conftest.py`:

```python
"""Shared fixtures for <module> tests."""

import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> MagicMock:
    return MagicMock(spec=Session)


@pytest.fixture
def sample_user() -> dict:
    return {
        "email": "test@example.com",
        "business_name": "Test Business",
        "timezone": "America/Sao_Paulo",
    }
```

**Key rule**: shared fixtures belong in `conftest.py`, NOT duplicated in each test file. If `test_user_service.py` and `test_invite_service.py` both need a db session mock -- that's a conftest fixture.

### Mocking Rules

Mock at **system boundaries only**:
- Database queries and session operations
- HTTP requests and API calls
- File I/O (when testing logic, not I/O itself)
- External service clients (email, payment, etc.)

**Do not mock**:
- Internal functions within the same module
- Data transformations or pure logic
- Pydantic model construction

**Patch limit**: if a test needs 5+ `@mock.patch` decorators, the test is testing implementation details. Refactor by:
- Extracting the logic being tested into a pure function
- Using dependency injection via parameters instead of patching globals
- Testing at a higher level where fewer mocks are needed

```python
# Good: mock at boundary
@patch("app.repositories.user_repo.UserRepository.get_by_email")
def test_returns_none_when_user_not_found(self, mock_get: MagicMock) -> None:
    mock_get.return_value = None
    result = user_service.find_user("nonexistent@example.com")
    assert result is None

# Bad: mock internal function
@patch("app.views.user_service._validate_slug")
def test_validates_slug(self, mock_validate: MagicMock) -> None:
    ...  # testing implementation, not behavior
```

### Parametrize for Variations

Use `@pytest.mark.parametrize` when testing the same logic with different inputs:

```python
@pytest.mark.parametrize(
    "business_name, expected_slug",
    [
        ("My Business", "my-business"),
        ("Café & Bar", "cafe-bar"),
        ("  Spaces  ", "spaces"),
    ],
)
def test_generates_slug_from_business_name(
    self, business_name: str, expected_slug: str
) -> None:
    result = generate_slug(business_name)
    assert result.startswith(expected_slug)
```

### Assertion Style

```python
# Good
assert result == expected_value
assert len(items) == 3
assert "error" in message

with pytest.raises(ValueError, match="invalid email"):
    process(bad_input)

mock_repo.create.assert_called_once_with(expected_data)

# Bad
self.assertEqual(result, expected_value)  # unittest style
self.assertTrue(len(items) == 3)          # unittest style
self.assertRaisesRegex(ValueError, ...)   # unittest style
assert result  # unclear what's being tested
```

### Anti-Patterns

Do NOT do these:

- **Duplicate fixtures** -- never copy-paste fixture setup into multiple test files. Put it in `conftest.py`
- **Separate test per enum value** -- if 3 values go through the same logic, use `@pytest.mark.parametrize`, not 3 identical test functions
- **Assert on internal method calls** -- test outcomes (return values, exceptions raised, state changes), not which internal methods were called
- **unittest.TestCase** -- never use `self.assertEqual`, `self.assertTrue`, `self.assertRaises`. Use plain `assert` and `pytest.raises`
- **>5 assertions in one test** -- split into separate tests, each testing one behavior

### What NOT to Test

- Pydantic model field definitions (Pydantic already validates)
- Simple pass-through functions with no logic
- Third-party library behavior
- Constants or enum definitions
- SQLAlchemy model column definitions
- FastAPI dependency injection wiring (test the dependencies themselves, not the framework)

## Step 3: Verify

After generating tests:

1. Run the tests: `mise test -- tests/<path>/test_<module>.py`
2. Fix any failures
3. Run lint: `mise lint-fix`
4. Report results to the user