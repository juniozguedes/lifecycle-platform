---
name: pr-reviewer
description: Reviews staged/changed code before pushing to GitHub, catching common patterns and mistakes.
---

# PR Reviewer -- Instructions

> **Prerequisites**: Read `AGENTS.md` in the repository root for the coding conventions to review against.

When the user invokes this skill, review the current git changes and flag issues based on the categories below and the rules in `AGENTS.md`.

## Agent Behavior Rules

- **NEVER** commit, push, merge, rebase, or perform any write git operations
- **NEVER** run `git commit`, `git push`, `git checkout`, `git reset`, or any destructive command
- The agent **may only** run read-only git commands: `git diff`, `git status`, `git log`, `git show`
- Do not modify any files unless the user explicitly asks for a fix
- Do not open PRs or interact with GitHub
- Present findings as a categorized review -- the user decides what to act on
- When suggesting a fix, show the code change but do not apply it unless asked

## How to Run

Inspect the current changes using:

```bash
git diff                    # unstaged changes
git diff --staged           # staged changes
git diff HEAD               # all changes vs last commit
git diff main...HEAD        # all changes on the branch vs main
```

Review each changed file against the categories below. Report findings grouped by file, with the category tag and a brief explanation.

## Review Categories

### Meaningless Comments

Comments should only explain non-obvious intent, trade-offs, or constraints. Do not add comments that merely restate what the code already says.

Bad:

```python
# This fetches auth
def fetch_auth() -> Any:

# Navigate to the login page
app.navigate("/login")
```

Good:

```python
# SQLite doesn't enforce FK constraints by default; enable per-connection
event.listen(engine, "connect", _set_sqlite_pragma)
```

Flag if: comments narrate what the function name or code line already communicates (e.g. `# Click the button` above a click call, `# Return the result` above `return`).

### Error Handling

Broad `except Exception` blocks can hide real errors and push them downstream. Exception handling should be specific about what failures are expected and why it's safe to continue.

Flag if: a bare `except Exception` catch-all is used without a clear justification for why all exception types should be swallowed.

### Resource Cleanup

Functions that open files, database sessions, or network connections must clean them up. Use context managers (`with` statements) or `try/finally`.

Flag if: resources are opened but not properly closed, or temp files are created but never cleaned up.

### Date/Time Handling

Use a consistent date/time library across the project. Avoid mixing raw `datetime` with higher-level libraries. Always be explicit about timezones.

Flag if: naive datetimes are created where timezone-aware ones are expected, or date parsing uses fragile string splitting instead of proper parsing.

### Use Regex for Path/String Parsing

When parsing paths, filenames, or structured strings, prefer regex over chains of `if`/`elif`/`split()` logic. Regex with named capture groups is more readable and robust.

Flag if: a function manually splits strings and uses conditional logic to extract parts that a simple regex could capture.

### Dead Code and Unused Symbols

**Ghost / unused functions**: Flag new or modified `def` / methods that are never called from anywhere visible in the change set (and no plausible entrypoint such as CLI registration or route decorator).

**Unused variables**: Flag assignments whose values are never read (except intentional discard patterns, e.g. `_ = ...` or loop variables named `_`).

**Unused imports**: Flag imports in changed files that are clearly unused after the edit.

### Typos and Naming

Check for English typos in variable names, function names, string literals, and decorator arguments. Common examples: `retur_value` instead of `return_value`, misspelled class names, etc.

Flag if: obvious typos exist in identifiers or string arguments.

### Logging Quality

Flag if: sensitive data (passwords, tokens, secrets) are logged, log levels are misused (e.g. `debug` for errors), or log messages provide no useful context (e.g. `logger.info("here")`).

### Test Quality

Flag if: tests assert on implementation details rather than behavior, tests have no assertions, test names don't describe the behavior being tested, or mock setup is duplicated across files instead of using `conftest.py` fixtures.

### Type Annotations

Flag if: new public functions or methods lack type annotations for parameters and return types.

## Output Format

Present the review as a list grouped by file:

```
## 

- **[Category]**: <description of the issue>
  <optional code snippet or suggested fix>
```

If no issues are found, say so. Don't invent problems.