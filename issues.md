You are a senior Python backend engineer with deep expertise in FastAPI, SQLAlchemy, Alembic, async Python, GitHub Actions, and production database migrations.

Your task is to fix all the issues listed below across multiple files.
The fixes must be correct, safe for production, and consistent with best practices.

❗ Global Rules

Do NOT ignore errors

Do NOT comment out logic unless explicitly instructed

Do NOT introduce breaking changes

Prefer safe migrations (backfill → alter)

Ensure all changes are idempotent and production-safe

Preserve data wherever possible

Update code, tests, and comments together

If something is ambiguous, choose the safest option

✅ Issues to Fix (Grouped by File)
📄 .github/workflows/migration-check.yml

Fail CI on test failure

Locate the step named "Run tests"

Remove continue-on-error: true OR set it to false

If temporarily needed, add a clear # TODO: comment explaining why and when it should be removed

Handle empty Alembic versions directory

The loop for file in alembic/versions/*.py must not fail when no files exist

Use one of:

shopt -s nullglob

OR check if the glob matched before iterating

Skip non-existent matches before calling python -m py_compile

Fix inverted migration naming validation

Accept files that match:

^[0-9a-f]{12}_[a-z0-9_]+\.py$


If a file does not match the regex and contains def upgrade,

Print Invalid migration naming: <file>

Exit with non-zero status

The workflow must fail on violations

Preserve Alembic exit code

Do NOT use command substitution that loses $?

Run Alembic, capture output to a temp file

Save exit code immediately

Read output afterward

Use the saved exit code for condition checks

📄 agents/standard/formatter.py

Revision cost is missing

_revise_paper updates token counts but not cost

Update it to return:

Either (revision_prompt_tokens, revision_completion_tokens)

OR a computed revision_cost

In formatter_node, compute cost using get_model_pricing(model)

Add revision cost to state.cost

Keep state.tokens_used logic intact

Fix None token arithmetic

Attributes like usage.prompt_tokens may exist but be None

Coalesce all numeric values with or 0

Ensure revision_tokens is always an int

📄 alembic.ini

Fix unclear truncate_slug_len comment

Rewrite it clearly to explain:

Default truncation can cause confusing/non-deterministic name collisions

This setting controls truncation length to avoid that

Fix empty sqlalchemy.url

Replace with ${DATABASE_URL}

Ensure Alembic can connect using environment variables

📄 alembic/versions/4745fd629317_initial_schema_creation.py

Reorder table creation

sources table must be created before contradictions

All FK targets must exist before constraints

Fix initial migration contradiction

The migration claims down_revision = None

But assumes existing tables

Choose ONE:

Convert it into a true initial migration

OR set correct down_revision and keep logic

Make the chain consistent and runnable on a fresh DB

Preserve server defaults

Do NOT remove defaults for:

users.id

users.is_active

users.created_at

users.updated_at

Retain DB defaults or explicitly define them

Fix NOT NULL on existing data

Before making agent_actions.task_id NOT NULL:

DELETE or UPDATE rows with NULLs

Then apply nullable=False

Prevent data loss

The migration drops:

subscriptions

sources

usage_logs

human_checkpoints

contradictions

Before dropping:

Preserve data via staging tables or INSERT-SELECT

Restore data in downgrade

Add ON DELETE CASCADE

Fix missing ondelete='CASCADE' for:

fk_agent_actions_task_id

fk_research_tasks_user_id

Fix enum NOT NULL additions

For users.subscription_status

For research_tasks.description

For research_tasks.research_depth

Use:

server_default → backfill → alter nullable=False

📄 api/dependencies.py

Narrow exception handling

Catch HTTPException as exc

Return None only for 401

Re-raise all other exceptions

📄 api/main.py

Make health check actually verify DB

Execute a lightweight query (SELECT 1)

Catch failures

Return "database": "connected" or "unreachable"

Do not crash endpoint

📄 core/config.py

Disable debug by default

Set debug: bool = False

Enable only via environment variable

Production must default to safe mode

📄 core/security.py

Do not leak internal errors

Replace detailed error messages with generic ones

Log full exceptions internally

Fix fragile audience parsing

Do NOT split strings manually

Use safe parsing or fallback logic

Fail authentication cleanly if invalid

Hide token parsing errors

Replace str(e) in HTTP 401 responses

Log exception internally

📄 database/connection.py

Remove unused imports

Remove event, NullPool

Fix SQLite async URL

Convert sqlite:// → sqlite+aiosqlite://

Only if driver not already specified

Ensure async engine works in dev/tests

📄 models/user.py

Remove hidden defaults

Remove default_factory for:

id

created_at

If needed, create a separate input/test schema

📄 requirements.txt

Remove duplicate httpx

Keep only one entry

Use the higher minimum version

📄 tests/conftest.py

Fix empty fixtures

Replace pass with:

pytest.skip(...)

OR implement real DB-backed fixtures

📄 tests/test_auth_complete.py

Fix async/sync mismatch

If using TestClient, make test synchronous

OR switch to httpx.AsyncClient + pytest.mark.asyncio

Fix placeholder tests

Either skip them explicitly

OR implement real async tests

Fix ineffective exception test

Replace pass inside pytest.raises

Actually trigger the mocked failure

📄 updates.md

Explain missing Phase 2

Add note explaining:

Phase 2 completed & removed

OR intentionally skipped

OR renumber phases