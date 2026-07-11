# OverwatcherPI: SQLite → Supabase (Postgres) Migration Plan

**Status:** Not started. Written alongside the PortfolioPi migration (same host, same pattern) so both can be executed with a consistent, proven approach. This plan reflects OverwatcherPI's actual current codebase, not an approximation — every table, job, and call site listed below was read directly from source, not inferred.

## Context

OverwatcherPI (Telegram bot + Streamlit dashboard, home network monitor) currently stores everything in a local SQLite file (`data/netmon.db`) on the Pi. Same motivation as PortfolioPi: reachability/alterability from anywhere, not just the Pi. Same sequence: **1) set up the Supabase connector → 2) migrate the data → 3) switch the app to Postgres → 4) sunset SQLite.**

**This migration is structurally simpler than PortfolioPi's in one major way, and about the same complexity in another:**

- **Simpler:** Every timestamp column across all 17 tables is a `REAL` Unix-epoch float (`time.time()`), not a `DATETIME` string. This eliminates PortfolioPi's entire class of "psycopg2 returns real datetime objects now, downstream code did string arithmetic/strptime on it" bugs — a `REAL`/`DOUBLE PRECISION` column round-trips as a plain Python `float` through both `aiosqlite` and `asyncpg`/`psycopg2`, no representation change at all. `dashboard/db.py`'s `pd.to_datetime(df['col'], unit='s')` calls keep working unmodified.
- **Simpler:** All DB logic lives in **one file** (`core/database.py`'s `DatabaseManager` singleton classmethod pattern), not scattered across 13 files like PortfolioPi. Far fewer call sites to translate.
- **About the same:** `docker-compose.yml`'s bot healthcheck and `core/scheduler.py`'s `db_backup_job` both shell out to SQLite directly (via CLI and via `sqlite3.Connection.backup()`, respectively) — same two things need Postgres-native replacements as in PortfolioPi.
- **New wrinkle not present in PortfolioPi:** several dynamic `IN (?,?,?)` clauses (built via `",".join("?" * len(items))`) — Postgres has a cleaner idiom for this (`= ANY($1::text[])` / `!= ALL($1::text[])` with a single array parameter) that should be used instead of manually renumbering `$n` placeholders for a variable-length list.
- **New wrinkle:** `bot/handlers.py`'s `health_handler` and `core/scheduler.py`'s `db_retention_job` both bypass the `DatabaseManager` classmethod wrappers and call `db.execute(...)` directly on the connection object returned by `DatabaseManager.get_db()` — these call sites need the same translation treatment even though they're not inside the `DatabaseManager` class itself.
- **New wrinkle:** `bot/handlers.py`'s `health_handler` also does `os.path.getsize(config.db_path)` to show DB file size in a `/health`-style command — a remote hosted DB has no local file size; either drop this line or replace it with a `pg_size_pretty(pg_database_size(current_database()))` query.
- **Favorable environment fact:** the `bot` and `sniffer` containers use `network_mode: host` (required for nmap ARP discovery / BlueZ D-Bus), meaning their DNS resolution goes through the host directly, not through Docker's bridge-network embedded DNS proxy — one less thing to suspect if connectivity issues come up during migration (unlike the red herring chased during PortfolioPi's migration, which turned out to be a DSN-parsing bug, not networking, but the host-network setup here removes even the possibility). The `dashboard` container is on the default bridge network with a published `127.0.0.1:8501` port — same as any other container in this respect.

**Key design decisions (same as PortfolioPi, for consistency):**
- Direct Postgres protocol: `asyncpg` for the bot (async, pooled via a new `core/db.py`), `psycopg2-binary` for the dashboard (sync, pooled via `psycopg2.pool.ThreadedConnectionPool`, matching the pattern already proven in PortfolioPi's `dashboard/db.py`).
- Supabase **Session Pooler** (port 5432), not Transaction Pooler or Direct — same IPv4/prepared-statement reasoning as PortfolioPi.
- **Percent-encode any `@`, `#`, or other URL-reserved character in the DB password** in `.env` — this exact issue cost significant time during the PortfolioPi migration (asyncpg's DSN parser mis-splits on a raw `@`, silently extracting a wrong hostname, which then fails DNS resolution with a generic, misleading "Name or service not known" error that looks like a network problem). Check this **first** if any connection attempt fails during Phase 1.
- Lightweight custom backup job (per-table gzip CSV export via `asyncpg.copy_from_query`) regardless of Supabase tier, replacing `db_backup_job`'s SQLite `.backup()` call — same reasoning as PortfolioPi (Free tier historically ships with no automated backups).
- Network restriction: reuse the same Supabase project's IP allowlist if this ends up sharing a project with PortfolioPi, or configure separately if it gets its own project — decide this at Phase 1 kickoff.
- Use `psql`'s `TRUNCATE ... RESTART IDENTITY` + explicit-id `INSERT` for the one-time data load, same as PortfolioPi's `migrate_to_supabase.py` pattern — reuse that script's structure almost directly, since the id/no-id table split logic already exists there.

---

## Full table inventory (17 tables, all read directly from `core/database.py`'s `_init_tables`)

```sql
-- All REAL columns are Unix-epoch timestamps (time.time()) — straightforward
-- REAL -> DOUBLE PRECISION mapping, zero date-parsing semantics involved.

CREATE TABLE IF NOT EXISTS network_devices (
    mac TEXT PRIMARY KEY,
    ip TEXT,
    vendor TEXT,
    hostname TEXT,
    first_seen DOUBLE PRECISION NOT NULL,
    last_seen DOUBLE PRECISION NOT NULL,
    is_active INTEGER DEFAULT 1,
    raw_mdns_name TEXT,
    raw_ssdp_server TEXT,
    raw_netbios_name TEXT,
    is_known INTEGER DEFAULT 0,
    banner_grab_attempted_at DOUBLE PRECISION,
    banner_grab_attempts INTEGER DEFAULT 0,
    friendly_name TEXT,
    device_type TEXT,
    owner TEXT
);
-- NOTE: the "is_known column if it doesn't exist" / "raw_mdns_name" / etc. ALTER
-- TABLE dance in _init_tables (lines 239-254 of the current file) is SQLite-era
-- ad-hoc schema versioning. For a fresh Postgres schema, just declare every
-- column up front as above — no ALTER TABLE migration logic needed at all.

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    scan_time DOUBLE PRECISION NOT NULL,
    device_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dns_queries (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    src_ip TEXT NOT NULL,
    query_name TEXT NOT NULL,
    query_type TEXT
);
CREATE INDEX IF NOT EXISTS idx_dns_queries_src_ts ON dns_queries(src_ip, timestamp);

CREATE TABLE IF NOT EXISTS bt_devices (
    address TEXT PRIMARY KEY,
    name TEXT,
    rssi INTEGER,
    last_seen DOUBLE PRECISION NOT NULL,
    manufacturer_data_hex TEXT,
    service_uuids TEXT,
    is_known INTEGER DEFAULT 0,
    tx_power INTEGER,
    rssi_history TEXT DEFAULT '[]',
    fingerprint TEXT
);
CREATE INDEX IF NOT EXISTS idx_bt_devices_fingerprint ON bt_devices(fingerprint);

CREATE TABLE IF NOT EXISTS oui_mappings (
    mac_prefix TEXT PRIMARY KEY,
    vendor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitored_hosts (
    ip TEXT PRIMARY KEY,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS device_ports (
    mac TEXT,
    port INTEGER,
    service TEXT,
    first_seen DOUBLE PRECISION NOT NULL,
    last_seen DOUBLE PRECISION NOT NULL,
    is_active INTEGER DEFAULT 1,
    PRIMARY KEY (mac, port)
);

CREATE TABLE IF NOT EXISTS port_history (
    mac TEXT,
    port INTEGER,
    service TEXT,
    event TEXT,
    timestamp DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_port_history_mac ON port_history(mac);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    related_id TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT,
    target TEXT,
    status TEXT,
    requester_chat_id BIGINT,
    created_at DOUBLE PRECISION,
    started_at DOUBLE PRECISION,
    finished_at DOUBLE PRECISION,
    result_summary TEXT,
    result_path TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS ble_alert_cooldown (
    vendor_key TEXT PRIMARY KEY,
    last_alert_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS honeypot_alert_cooldown (
    src_ip TEXT PRIMARY KEY,
    last_alert_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS resource_alert_cooldown (
    metric_key TEXT PRIMARY KEY,
    last_alert_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS latency_samples (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    target TEXT NOT NULL,
    loss_pct DOUBLE PRECISION,
    jitter_ms DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS deferred_scans (
    mac TEXT PRIMARY KEY,
    ip TEXT NOT NULL,
    queued_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS job_heartbeats (
    job_name TEXT PRIMARY KEY,
    last_run_at DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS device_maintenance (
    mac TEXT PRIMARY KEY,
    until_timestamp DOUBLE PRECISION NOT NULL,
    reason TEXT
);
```

No foreign keys exist anywhere despite the SQLite-side `PRAGMA foreign_keys=ON` (that pragma is currently a no-op — nothing declares a `REFERENCES` clause). Drop it along with `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and `PRAGMA cache_size=-65536` when moving to Postgres — none apply.

## SQLite-specific syntax needing translation

| Pattern | Location(s) | Postgres equivalent |
|---|---|---|
| `?` placeholders everywhere | All of `core/database.py`, `core/scheduler.py`'s raw calls, `bot/handlers.py`'s raw calls | `$1, $2, ...` (asyncpg) |
| `?` placeholders in dashboard | All of `dashboard/db.py` (12 query functions) | `%s` (psycopg2) |
| `INSERT OR REPLACE INTO oui_mappings` | `core/database.py:532` (`bulk_insert_oui`) | `INSERT ... ON CONFLICT (mac_prefix) DO UPDATE SET vendor = excluded.vendor` |
| `INSERT OR REPLACE INTO monitored_hosts` | `core/database.py:511` (`add_monitored_host`) | `INSERT ... ON CONFLICT (ip) DO UPDATE SET is_active = excluded.is_active` |
| `INSERT OR REPLACE INTO deferred_scans` | `core/database.py:722` (`queue_deferred_scan`) | `INSERT ... ON CONFLICT (mac) DO UPDATE SET ip = excluded.ip, queued_at = excluded.queued_at` |
| `INSERT ... ON CONFLICT(pk) DO UPDATE SET ... CASE WHEN excluded.col != '' THEN ... ELSE table.col END` | `upsert_network_devices`, `upsert_bt_devices`, `upsert_device_ports`, `should_alert_ble_vendor`, `should_alert_honeypot`, `should_alert_resource`, `record_scan_heartbeat`, `set_maintenance` | **Already Postgres-compatible syntax** (SQLite borrowed `ON CONFLICT` from Postgres) — only the `?`→`$n` placeholder conversion is needed, no structural change. |
| Dynamic `IN ({",".join("?" * len(x))})` | `upsert_network_devices` (gone_macs query), `upsert_bt_devices` (existing_histories query), `upsert_device_ports` (gone_ports query) | Replace with a single array parameter: `WHERE mac != ALL($1::text[])` instead of manually building/renumbering `IN ($1,$2,$3,...)`. Cleaner and avoids off-by-one placeholder bugs entirely. |
| `PRAGMA table_info(table)` ad-hoc ALTER TABLE migration dance | `core/database.py:239-283` | Not needed at all — declare every column in the initial `CREATE TABLE` (this is a one-time fresh schema creation, not an evolving multi-version one). |
| `sqlite3.Connection.backup()` (native SQLite hot-backup API) | `core/scheduler.py:641-669` (`db_backup_job`) | No equivalent — replace with per-table gzip CSV export via `asyncpg.copy_from_query`, same pattern as PortfolioPi's rewritten `db_backup_job`. |
| `sqlite3` CLI-based Docker healthcheck | `docker-compose.yml`'s `bot` service (inline `python -c "import sqlite3..."`) | New `healthcheck.py` using `asyncpg`, checking `job_heartbeats` for `fast_sweep`/`service_watchdog`/`resource_health` all within 900s — same three-job freshness check, translated. |
| `os.path.getsize(config.db_path)` (DB file size) | `bot/handlers.py`'s `health_handler` | No local file exists anymore — either drop this line, or replace with `SELECT pg_size_pretty(pg_database_size(current_database()))`. |
| Raw `db.execute(...)` bypassing `DatabaseManager` classmethods | `core/scheduler.py`'s `db_retention_job`; `bot/handlers.py`'s `health_handler` | Same pool-based translation as everywhere else — these aren't inside the `DatabaseManager` class, so don't forget them in a file-by-file pass. |
| `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)` (dashboard read-only mode) | `dashboard/db.py:15` | Drop the URI/mode=ro trick — use a plain `psycopg2.connect(dsn=...)` (optionally via a Postgres read-only role if enforcement matters, but not required). |

## Files touched, by phase (mirrors PortfolioPi's phase structure)

- **Phase 1 (setup connector):** `config.py` (add `database_url: SecretStr`), `.env.example`/`.env` (add `DATABASE_URL=`), `requirements.txt` (add `asyncpg`, `psycopg2-binary`), `docker-compose.yml` (add `DATABASE_URL` to whichever services need it — `bot` already gets `env_file: .env` wholesale; `dashboard` also uses `env_file: .env` here, unlike PortfolioPi's dashboard which needed an explicit `environment:` entry — **verify this against the actual file before assuming**, since PortfolioPi's dashboard config gotcha was exactly this kind of unchecked assumption), new `scripts/init_supabase_schema.py` (the 17-table DDL above).
- **Phase 2 (migrate data):** new `scripts/migrate_to_supabase.py` — can largely copy PortfolioPi's script structure (it already handles both id-based and non-id-based tables). Table list here: `network_devices`, `bt_devices`, `oui_mappings`, `monitored_hosts`, `job_heartbeats`, `ble_alert_cooldown`, `honeypot_alert_cooldown`, `resource_alert_cooldown`, `device_maintenance` are all PK-keyed (no surrogate `id`, `has_id=False`); `scan_history`, `dns_queries`, `device_ports` (composite PK `mac,port` — also `has_id=False`), `port_history` (no PK at all declared — just insert in whatever order, no identity sequence to fix), `events`, `jobs` (`id` is `TEXT PRIMARY KEY`, not a surrogate integer — also `has_id=False`, order by `created_at` instead), `latency_samples`, `deferred_scans` are the rest.
- **Phase 3 (switch to Postgres):** new `core/db.py` (asyncpg pool, identical pattern to PortfolioPi's), rewritten `core/database.py` (the whole `DatabaseManager` class — every classmethod), rewritten `core/scheduler.py` (`db_retention_job`'s raw calls, `db_backup_job`'s full replacement), rewritten `bot/handlers.py` (`health_handler`'s raw calls + DB-size line), rewritten `dashboard/db.py` (all 12 functions, `sqlite3`→`psycopg2`), new `healthcheck.py`, `docker-compose.yml` (bot healthcheck), `main.py` (wherever `DatabaseManager`/pool gets initialized at startup — **check this file specifically for the same "forgot to call init_pool()" mistake made during PortfolioPi's Phase 3**), `tests/test_database.py` (currently points `config.db_path` at a temp SQLite file for test isolation — needs a test-Postgres-schema or mocking strategy instead).
- **Phase 4 (sunset SQLite):** remove `aiosqlite` from `requirements.txt`, archive `data/netmon.db` + `data/backups/*.db` off the Pi, update any docs (`docs/docker.md` is referenced at the top of `docker-compose.yml` and likely documents the SQLite-era setup — check it).

## Verification approach (same rigor as PortfolioPi)

1. **Before writing any Postgres-side code**, run the schema-init script standalone and confirm all 17 tables + 3 indexes exist via Supabase's Table Editor or `information_schema`.
2. **After the data migration script**, verify row counts + a relevant "MAX" check per table match between SQLite and Postgres (row counts, plus e.g. `MAX(last_seen)` for `network_devices`, `MAX(timestamp)` for `events`/`dns_queries`) — don't just trust the migration script's own log output.
3. **After Phase 3's rewrite, before cutover:** run a syntax check (`ast.parse`) and a real import test (catches missing deps — remember the PortfolioPi `yfinance` lesson: a truly clean `docker compose build` from `requirements.txt` can surface dependencies that were silently present in an old image but never declared) inside the built image, then a functional pool-init + `DatabaseManager._init_tables()` dry run against live Supabase, **before** touching the running containers.
4. **Cutover runbook:** same as PortfolioPi — `docker compose down` (all three: bot, sniffer, dashboard — plus caddy stays up since it doesn't touch the DB), final `migrate_to_supabase.py --truncate` reload, `docker compose up -d`, then smoke-test: `/status`-equivalent Telegram command, dashboard pages load, a manual `fast_sweep_job` invocation completes and writes to `network_devices`/`scan_history` correctly, `db_retention_job` and `db_backup_job` both run without crashing (these are the two most likely to have been missed in a first pass, based on the PortfolioPi experience where the equivalent jobs needed a second look).
5. **Don't trust `docker compose build`'s own exit status alone** — verify the built image actually contains the new code (`docker run --rm --network none <image> grep ...`) before running anything against it. This exact mistake (editing/deploying a file via `scp` without rebuilding, then being confused why a live-tested "fix" had no effect) cost real time twice during PortfolioPi's Phase 3.

## Open questions to resolve before starting

1. Same Supabase project as PortfolioPi, or a separate one? (Separate is probably cleaner — these are unrelated data domains, and keeping them in separate projects avoids any accidental cross-contamination or one project's outage taking down both apps.)
2. Backup strategy: same "lightweight custom job regardless of tier" default as PortfolioPi, unless the tier decision from that migration already settled this project-wide.
3. Network allowlist: if a separate Supabase project, needs its own IP restriction setup (same Pi public IP as before, unless it's changed).
