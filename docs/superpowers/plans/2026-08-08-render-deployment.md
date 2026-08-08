# Render Deployment (Docker, Neon Postgres, WhiteNoise) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (chosen workflow in this project) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ledger deploy cleanly to Render's free tier: a Dockerfile, `render.yaml`, production requirements, and a settings split with env-based `SECRET_KEY`/`DEBUG`, Neon Postgres via `dj-database-url`, and WhiteNoise static files.

**Architecture:** Split `config/settings.py` into a `config/settings/` package — `base.py` (shared), `development.py` (SQLite, hardcoded dev key, the default), `production.py` (everything from env, fails fast on missing `SECRET_KEY`/`DATABASE_URL`). The Docker image installs `requirements.txt`, runs `collectstatic` at build time under production settings with placeholder env values, and starts via an entrypoint that migrates then execs gunicorn — Render's free tier has no `preDeploy` hook, so migrations run at container boot. `render.yaml` is a Blueprint: docker runtime, free plan, generated `SECRET_KEY`, `DATABASE_URL` entered in the dashboard (Neon connection string, never committed).

**Tech Stack:** Django 6.1, gunicorn 26, WhiteNoise 6.12 (CompressedManifestStaticFilesStorage), dj-database-url 3.1, psycopg 3.3 (binary), Docker `python:3.14-slim`, Render free tier, Neon Postgres.

## Context

The full app (engine + web UI, 68 tests) lives on branch `worktree-ledger-web-ui`, pushed to origin; its PR is pending. The user chose to **continue on this same branch in the existing worktree** (`/home/oscar/Projects/Ledger/.claude/worktrees/ledger-web-ui`) — do not create a new worktree or branch. The user also chose **`python:3.14-slim`** for the image (latest stable; local venv is 3.12 — all four new deps support 3.10–3.14).

Current state that matters:
- `config/settings.py` is a single file: dev `SECRET_KEY` hardcoded, `DEBUG = True`, SQLite, `TEMPLATES["DIRS"] = [BASE_DIR / "templates"]`, `AUTH_USER_MODEL = "accounts.User"`, `LOGIN_URL`/`LOGIN_REDIRECT_URL`/`LOGOUT_REDIRECT_URL` at the bottom, a `MAILERS` console-backend block (stock Django 6.1). No `STATIC_ROOT`, no WhiteNoise.
- `manage.py`, `config/wsgi.py`, `config/asgi.py` all default `DJANGO_SETTINGS_MODULE` to `"config.settings"` — after the split they must default to `"config.settings.development"`.
- `requirements.txt` contains only `Django>=6.1,<6.2`; `requirements-dev.txt` is `-r requirements.txt` + `ruff`.
- ruff config in `pyproject.toml`: `select = ["E", "F", "I", "B", "UP", "DJ"]`, line-length 100 — star imports in settings modules need `# noqa: F403`.
- `.gitignore` lacks `staticfiles/`.
- PyPI latest (verified 2026-08-08): gunicorn 26.0.0, whitenoise 6.12.0, dj-database-url 3.1.2, psycopg 3.3.4. WhiteNoise 6.12's classifiers list Django ≤6.0 only because Django 6.1 shipped days ago — WhiteNoise is settings-level and version-agnostic here; not a defect.
- Render free tier specifics: no `preDeploy`/release phase (migrate in the entrypoint); the app must listen on `$PORT`; Render injects `RENDER_EXTERNAL_HOSTNAME` (the `*.onrender.com` host) into the env; gunicorn reads `WEB_CONCURRENCY` for its worker count automatically.

## Global Constraints

- Work in the existing worktree `/home/oscar/Projects/Ledger/.claude/worktrees/ledger-web-ui` on branch `worktree-ledger-web-ui` — no new worktree, no new branch.
- Tools: `.venv/bin/python`, `.venv/bin/pip`, `.venv/bin/ruff`.
- Django pin stays `Django>=6.1,<6.2`. New production deps are exactly: `gunicorn>=26,<27`, `whitenoise>=6.12,<7`, `dj-database-url>=3.1,<4`, `psycopg[binary]>=3.3,<4`. No other new packages (PyYAML may be pip-installed into the venv for a one-off `render.yaml` validation but never added to any requirements file).
- Docker base image: `python:3.14-slim` (user decision).
- No secrets in the repo: `production.py` reads `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`, `RENDER_EXTERNAL_HOSTNAME` from env only, and raises `ImproperlyConfigured` when `SECRET_KEY` or `DATABASE_URL` is missing.
- Settings module names (exact): `config.settings.base`, `config.settings.development` (the default everywhere), `config.settings.production` (selected only via `DJANGO_SETTINGS_MODULE`).
- The existing 68 tests must stay green under development settings after every task.
- TDD per task where the deliverable is testable: failing test → RED run → implement → GREEN run → commit.
- Every commit message ends with the trailer: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## File Structure

```
requirements.txt                 # + gunicorn, whitenoise, dj-database-url, psycopg (Task 1)
config/settings/
├── __init__.py                  # empty
├── base.py                      # moved from config/settings.py; shared settings, WhiteNoise middleware, STATIC_ROOT
├── development.py               # SQLite, dev key, DEBUG=True (default settings module)
└── production.py                # env-driven; dj-database-url; manifest storage; security headers
config/test_production_settings.py  # env-driven import tests (no DB needed)
manage.py, config/wsgi.py, config/asgi.py  # default → config.settings.development
.gitignore                       # + staticfiles/
Dockerfile                       # python:3.14-slim, build-time collectstatic, non-root
docker-entrypoint.sh             # migrate + exec gunicorn on $PORT
.dockerignore
render.yaml                      # Blueprint: docker runtime, free plan, env vars
README.md                        # + Deploy section
docs/superpowers/plans/2026-08-08-render-deployment.md  # committed copy of this plan
```

---

### Task 1: Production dependencies

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: existing `requirements-dev.txt` (`-r requirements.txt` + `ruff`) — unchanged.
- Produces: importable `gunicorn`, `whitenoise`, `dj_database_url`, `psycopg` in the venv; Tasks 2–3 rely on these exact distributions.

- [ ] **Step 1: Replace `requirements.txt` with:**

```
Django>=6.1,<6.2
gunicorn>=26,<27
whitenoise>=6.12,<7
dj-database-url>=3.1,<4
psycopg[binary]>=3.3,<4
```

- [ ] **Step 2: Install and verify**

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pip check
.venv/bin/python -c "import gunicorn, whitenoise, dj_database_url, psycopg; print('deps ok')"
```

Expected: install succeeds, `pip check` reports no broken requirements, `deps ok` prints.

- [ ] **Step 3: Run the full suite to confirm nothing regressed**

Run: `.venv/bin/python manage.py test`
Expected: 68/68 PASS.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add production dependencies (gunicorn, whitenoise, dj-database-url, psycopg)"
```

---

### Task 2: Settings split (base / development / production)

**Files:**
- Create: `config/settings/__init__.py`, `config/settings/development.py`, `config/settings/production.py`, `config/test_production_settings.py`
- Move: `config/settings.py` → `config/settings/base.py` (via `git mv`, then edit)
- Modify: `manage.py:10`, `config/wsgi.py:14`, `config/asgi.py:14`, `.gitignore`

**Interfaces:**
- Consumes: deps from Task 1 (`dj_database_url`, `whitenoise`).
- Produces: settings modules `config.settings.development` (default) and `config.settings.production`; `base.py` exports `BASE_DIR`, `MIDDLEWARE` (WhiteNoise second), `STATIC_ROOT = BASE_DIR / "staticfiles"`. Task 3's Dockerfile runs `collectstatic` with `DJANGO_SETTINGS_MODULE=config.settings.production` plus placeholder `SECRET_KEY`/`DATABASE_URL` — production.py must import cleanly with any syntactically valid `DATABASE_URL` and no database connection.

- [ ] **Step 1: Write the failing tests** — create `config/test_production_settings.py`:

```python
"""Import-level tests for config.settings.production — no database needed."""

import importlib
import os
import sys
import unittest
from unittest import mock

from django.core.exceptions import ImproperlyConfigured

MODULE = "config.settings.production"

BASE_ENV = {
    "SECRET_KEY": "test-secret-key",
    "DATABASE_URL": "postgresql://user:pass@db.example.com:5432/ledger",
}


def load_production(**overrides):
    """Import production settings fresh under a controlled environment.

    Pass VAR=None to unset a variable from the base test environment.
    """
    env = {k: v for k, v in {**BASE_ENV, **overrides}.items() if v is not None}
    sys.modules.pop(MODULE, None)
    with mock.patch.dict(os.environ, env, clear=True):
        try:
            return importlib.import_module(MODULE)
        finally:
            sys.modules.pop(MODULE, None)


class ProductionSettingsTests(unittest.TestCase):
    def test_missing_secret_key_raises(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "SECRET_KEY"):
            load_production(SECRET_KEY=None)

    def test_missing_database_url_raises(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "DATABASE_URL"):
            load_production(DATABASE_URL=None)

    def test_debug_defaults_off(self):
        self.assertFalse(load_production().DEBUG)

    def test_debug_enabled_from_env(self):
        self.assertTrue(load_production(DEBUG="true").DEBUG)

    def test_database_url_parsed_with_ssl_and_pooling(self):
        db = load_production().DATABASES["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(db["NAME"], "ledger")
        self.assertEqual(db["CONN_MAX_AGE"], 600)
        self.assertEqual(db["OPTIONS"]["sslmode"], "require")

    def test_render_hostname_joins_allowed_hosts_and_csrf_origins(self):
        settings = load_production(RENDER_EXTERNAL_HOSTNAME="ledger.onrender.com")
        self.assertIn("ledger.onrender.com", settings.ALLOWED_HOSTS)
        self.assertIn("https://ledger.onrender.com", settings.CSRF_TRUSTED_ORIGINS)

    def test_allowed_hosts_env_is_comma_separated(self):
        settings = load_production(ALLOWED_HOSTS="a.example.com,b.example.com")
        self.assertIn("a.example.com", settings.ALLOWED_HOSTS)
        self.assertIn("b.example.com", settings.ALLOWED_HOSTS)

    def test_whitenoise_manifest_storage(self):
        settings = load_production()
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_whitenoise_middleware_directly_after_security(self):
        settings = load_production()
        index = settings.MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
        self.assertEqual(
            settings.MIDDLEWARE[index + 1], "whitenoise.middleware.WhiteNoiseMiddleware"
        )

    def test_security_settings(self):
        settings = load_production()
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertTrue(settings.SECURE_SSL_REDIRECT)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertGreater(settings.SECURE_HSTS_SECONDS, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test config -v 2`
Expected: every test ERRORs with `ModuleNotFoundError: No module named 'config.settings.production'` (`config.settings` is still a module, not a package).

- [ ] **Step 3: Move the settings file into a package**

```bash
mkdir config/settings
git mv config/settings.py config/settings/base.py
touch config/settings/__init__.py
```

- [ ] **Step 4: Edit `config/settings/base.py`** — four changes, leaving everything else (INSTALLED_APPS, TEMPLATES, password validators, i18n, MAILERS, AUTH_USER_MODEL, LOGIN_* settings) exactly as is:

1. `BASE_DIR` gains one `.parent` (file is one level deeper):

```python
BASE_DIR = Path(__file__).resolve().parent.parent.parent
```

2. Delete the `SECRET_KEY = ...`, `DEBUG = True`, and `ALLOWED_HOSTS = []` lines (and their `# SECURITY WARNING` comments) — they move to the child modules.

3. Delete the whole `DATABASES = {...}` block and its comment header (moves to `development.py`).

4. In `MIDDLEWARE`, insert WhiteNoise directly after SecurityMiddleware:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

and under the `# Static files` section, after `STATIC_URL = "static/"`, add:

```python
STATIC_ROOT = BASE_DIR / "staticfiles"
```

- [ ] **Step 5: Create `config/settings/development.py`:**

```python
"""Development settings — SQLite, hardcoded key, DEBUG on. The default module."""

from .base import *  # noqa: F403
from .base import BASE_DIR

# SECURITY WARNING: dev-only key; production reads SECRET_KEY from the environment.
SECRET_KEY = "django-insecure-vto31yznvllwxlu$bmewk$2_)w=h#5$q&7#1(qszww$a5&g-1$"

DEBUG = True

ALLOWED_HOSTS = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

- [ ] **Step 6: Create `config/settings/production.py`:**

```python
"""Production settings — configured entirely from environment variables."""

import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set the SECRET_KEY environment variable.")

DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [host for host in os.environ.get("ALLOWED_HOSTS", "").split(",") if host]

# Render injects the app's public hostname (e.g. ledger.onrender.com).
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

DATABASES = {"default": dj_database_url.config(conn_max_age=600, ssl_require=True)}
if not DATABASES["default"]:
    raise ImproperlyConfigured("Set the DATABASE_URL environment variable.")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Render terminates TLS at its proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
```

- [ ] **Step 7: Point the default settings module at development** — in each of `manage.py` (line 10), `config/wsgi.py` (line 14), `config/asgi.py` (line 14), change:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

to:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
```

- [ ] **Step 8: Ignore collected statics** — append to `.gitignore`:

```
staticfiles/
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test -v 2`
Expected: all PASS — 68 existing + 10 new = 78. (The new tests run without touching the database; existing tests still use development/SQLite settings.)

- [ ] **Step 10: Deploy check under production settings**

```bash
SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
DATABASE_URL="postgresql://user:pass@db.example.com:5432/ledger" \
DJANGO_SETTINGS_MODULE=config.settings.production \
.venv/bin/python manage.py check --deploy
```

Expected: system check passes. The only acceptable warning is `security.W021` (HSTS preload not set — `onrender.com` is on the Public Suffix List, so preload does not apply). Any other warning is a finding to fix.

- [ ] **Step 11: Lint and commit**

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git add config manage.py .gitignore
git commit -m "feat: split settings into base/development/production with env-driven prod config"
```

---

### Task 3: Dockerfile, entrypoint, .dockerignore

**Files:**
- Create: `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore`

**Interfaces:**
- Consumes: `requirements.txt` (Task 1); `config.settings.production` importable with placeholder env and no DB connection, `STATIC_ROOT = staticfiles/` (Task 2); `config/wsgi.py` module path `config.wsgi:application`.
- Produces: image listening on `$PORT` (default 8000) that migrates at boot; Task 4's `render.yaml` points at this `Dockerfile`. Worker count comes from the `WEB_CONCURRENCY` env var (gunicorn reads it natively — the entrypoint does not hardcode workers).

- [ ] **Step 1: Create `docker-entrypoint.sh`:**

```sh
#!/bin/sh
set -e

python manage.py migrate --noinput
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
```

Make it executable (the Docker `CMD` needs the exec bit preserved in git):

```bash
chmod +x docker-entrypoint.sh
```

- [ ] **Step 2: Create `Dockerfile`:**

```dockerfile
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic imports production settings but needs no real secrets or database.
RUN SECRET_KEY=build-placeholder \
    DATABASE_URL=postgresql://build:build@localhost/build \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    python manage.py collectstatic --noinput

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
```

- [ ] **Step 3: Create `.dockerignore`:**

```
.venv/
.git/
.gitignore
__pycache__/
*.py[cod]
db.sqlite3
staticfiles/
.ruff_cache/
.superpowers/
docs/
Dockerfile
.dockerignore
render.yaml
README.md
```

- [ ] **Step 4: Prove the build-time collectstatic line works** (this is the test for the Dockerfile's only non-boilerplate step — run it locally exactly as the image will):

```bash
rm -rf staticfiles
SECRET_KEY=build-placeholder \
DATABASE_URL=postgresql://build:build@localhost/build \
DJANGO_SETTINGS_MODULE=config.settings.production \
.venv/bin/python manage.py collectstatic --noinput
ls staticfiles/staticfiles.json
```

Expected: "N static files copied … , M post-processed." with no database connection attempted, and the WhiteNoise manifest `staticfiles/staticfiles.json` exists. Then clean up: `rm -rf staticfiles`.

- [ ] **Step 5: Build the image if Docker is available**

```bash
command -v docker && docker build -t ledger:local . || echo "docker not available - skipping image build"
```

Expected if Docker exists: build succeeds through the collectstatic layer. If Docker is unavailable, validate what can be validated — `sh -n docker-entrypoint.sh` exits 0 — and record the skipped build as a concern in the report.

- [ ] **Step 6: Verify entrypoint syntax and executable bit**

```bash
sh -n docker-entrypoint.sh
git add Dockerfile docker-entrypoint.sh .dockerignore
git ls-files --stage docker-entrypoint.sh
```

Expected: `sh -n` exits 0; the staged mode for `docker-entrypoint.sh` is `100755`.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat: Dockerfile with build-time collectstatic and migrate-then-gunicorn entrypoint"
```

---

### Task 4: render.yaml, README deploy section, final sweep

**Files:**
- Create: `render.yaml`, `docs/superpowers/plans/2026-08-08-render-deployment.md` (copy of this plan)
- Modify: `README.md`

**Interfaces:**
- Consumes: `Dockerfile` (Task 3), settings module name `config.settings.production` (Task 2).
- Produces: Render Blueprint deployable via "New → Blueprint"; the only manual input at deploy time is `DATABASE_URL` (`sync: false`).

- [ ] **Step 1: Create `render.yaml`:**

```yaml
services:
  - type: web
    name: ledger
    runtime: docker
    plan: free
    healthCheckPath: /accounts/login/
    autoDeploy: true
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: config.settings.production
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        sync: false
      - key: WEB_CONCURRENCY
        value: "2"
```

(`healthCheckPath` targets the login page — it returns 200 without auth. `DATABASE_URL` with `sync: false` is prompted for in the Render dashboard: the Neon connection string. `RENDER_EXTERNAL_HOSTNAME` is injected by Render automatically; production settings already consume it.)

- [ ] **Step 2: Validate the YAML parses**

```bash
.venv/bin/pip install --quiet pyyaml
.venv/bin/python -c "import yaml; print(yaml.safe_load(open('render.yaml'))['services'][0]['runtime'])"
```

Expected: prints `docker`. (PyYAML is a one-off validation tool — do NOT add it to any requirements file.)

- [ ] **Step 3: Update `README.md`** — two edits.

In the `## Tech` section, append one bullet:

```markdown
- Deploys to Render (free tier) via Docker — gunicorn + WhiteNoise, Neon Postgres
```

After the `## Run it` section (before `## Tests`), insert:

```markdown
## Deploy (Render + Neon)

1. Create a free Postgres database at [neon.tech](https://neon.tech) and copy its connection string.
2. On [Render](https://render.com), choose **New → Blueprint** and point it at this repo — `render.yaml` provisions a free web service built from the `Dockerfile`.
3. When prompted, set `DATABASE_URL` to the Neon connection string.

Migrations run automatically on each deploy; static files are served by WhiteNoise.
```

- [ ] **Step 4: Commit the plan record** — copy the plan file from `/home/oscar/.claude/plans/build-the-core-debt-splitting-eager-pike.md` to `docs/superpowers/plans/2026-08-08-render-deployment.md`.

- [ ] **Step 5: Run the FULL sweep**

```bash
.venv/bin/python manage.py test -v 2
.venv/bin/ruff check .
.venv/bin/ruff format .
.venv/bin/python manage.py check
SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
DATABASE_URL="postgresql://user:pass@db.example.com:5432/ledger" \
DJANGO_SETTINGS_MODULE=config.settings.production \
.venv/bin/python manage.py check --deploy
```

Expected: 78 tests PASS, ruff clean, dev check clean, deploy check clean except the acceptable `security.W021`. If `ruff format` changed files, re-run the test suite once.

- [ ] **Step 6: Commit**

```bash
git add render.yaml README.md docs/superpowers/plans/2026-08-08-render-deployment.md
git commit -m "feat: Render blueprint, deploy docs, and plan record"
```

---

## Verification (end-to-end)

1. `.venv/bin/python manage.py test -v 2` — 78 tests green under development settings.
2. Production settings behave correctly without any deployment: the Task 2 test file proves fail-fast on missing `SECRET_KEY`/`DATABASE_URL`, Postgres URL parsing with `sslmode=require` and `CONN_MAX_AGE=600`, Render hostname → `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`, manifest storage, and the security header block.
3. `manage.py check --deploy` under production env: clean except `security.W021` (HSTS preload — inapplicable on `onrender.com`).
4. Local collectstatic simulation of the Docker build layer produces `staticfiles/staticfiles.json` with zero database traffic.
5. `docker build` succeeds if Docker is present (best-effort locally; Render performs the authoritative build).
6. Spec cross-check: Dockerfile (Task 3) ✓; `render.yaml` (Task 4) ✓; `requirements.txt` (Task 1) ✓; settings split with env-based `SECRET_KEY`/`DEBUG` (Task 2) ✓; `DATABASE_URL` for Neon via `dj-database-url` (Task 2, `ssl_require=True` for Neon's mandatory TLS) ✓; WhiteNoise static files (Tasks 2–3) ✓; Render free tier fit: `plan: free`, migrations at container boot because free tier lacks `preDeploy`, single instance so boot-time migrate is safe ✓.
7. After the branch deploys for real: sign up, create a group, add an expense — confirms Postgres connectivity, static assets, and CSRF origins in one pass.
