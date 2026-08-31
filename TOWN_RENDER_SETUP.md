# CUSTOMS AGENT TOWN — Dedicated Render Service

TOWN now lives in its own GitHub repository:

- `geminifoto0004-collab/flask-town`

It is intentionally separated from the main Flask/ORDER repository. The two
Render services may connect to the same TiDB database, while TOWN code and TOWN
tables remain logically isolated.

## Render Web Service

Configure the new Render Web Service with:

- Repository: `geminifoto0004-collab/flask-town`
- Build Command: `pip install -r requirements-town.txt`
- Start Command: `gunicorn town_app:app`
- Health Check Path: `/health`

Opening the service root redirects to `/customs-town`.

`requirements-town.txt` intentionally omits ORDER, Playwright, B2, report/PDF,
pandas and other main-service dependencies so the dedicated TOWN build stays
small and isolated.

## Required environment variables

Set secrets only in Render Environment settings. Do not commit secret values.

### TOWN / AI

- `DEEPSEEK_API_KEY` — required for AI decisions
- `TOWN_ADMIN_PASSWORD` — required for TOWN admin controls
- `TOWN_SECRET_KEY` — required/recommended; stable Flask session secret

Optional:

- `TOWN_AI_MODEL=deepseek-chat` — defaults to `deepseek-chat`
- `TOWN_STATE_DIR=/tmp/customs_agent_town` — local fallback files only; TiDB is
  authoritative for shared world/dialogue state

### Shared TiDB

Use the SAME TiDB connection values as the main Flask service if both services
should share one TiDB database.

Recommended single-URL configuration:

- `DATABASE_TYPE=tidb`
- `DATABASE_URL=mysql://USER:PASSWORD@HOST:4000/DATABASE?ssl_mode=REQUIRED`

Or use split variables:

- `DATABASE_TYPE=tidb`
- `DB_HOST`
- `DB_PORT=4000`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`

Supported aliases are also available:

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`

Optional for split-variable configurations when the host name does not already
identify TiDB Cloud:

- `DB_SSL_MODE=REQUIRED`

The standalone database adapter uses a small PyMySQL/DBUtils connection pool and
does not import the main Flask application's config/auth/email code.

## Shared TiDB tables used by TOWN

The TOWN runtime creates its own tables with `CREATE TABLE IF NOT EXISTS`:

- `town_world_state`
- `town_dialogue_messages`

These live in the same TiDB database as the main Flask tables but are used by
TOWN only.

## Isolation guarantee

`town_app.py` starts only the TOWN runtime. The standalone repository does not
mount ORDER, crawler jobs, B2 helpers, container services, report/PDF code, or
the main authorization application.

The main Render continues to use the separate `geminifoto0004-collab/flask`
repository.

## Current TOWN runtime

The standalone entry uses the stable runtime chain imported from source commit
`bfa530c287c19a22f883035e17b243630902f230`: world state, profiles, shifts,
generic entities, relationships, scenes, TiDB world/dialogue, admin commands,
and browser patches.

The repository was verified in GitHub Actions by installing
`requirements-town.txt` and importing `town_app`; `/health`, `/customs-town`, and
`/api/town/*` routes loaded successfully.
