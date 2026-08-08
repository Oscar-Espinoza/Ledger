# Ledger

Split group expenses and settle debts with the fewest payments.

Create a group, invite members by username, and record who paid for what —
split equally, by exact amounts, or by percentages, always exact to the cent.
Ledger tracks everyone's net balance and suggests the minimal set of payments
to settle up.

## Tech

- Python 3.12 · Django 6.1 (class-based views, ModelForms, custom user model, admin)
- SQLite for development · Bootstrap 5 via CDN (no build step) · ruff
- All money logic lives in `ledger/services.py` (`Decimal`-exact rounding,
  greedy min-cash-flow settlement), covered by the Django test suite
- Deploys to Render (free tier) via Docker — gunicorn + WhiteNoise, Neon Postgres

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Sign up at http://127.0.0.1:8000/accounts/signup/ and create your first group.

## Deploy (Render + Neon)

1. Create a free Postgres database at [neon.tech](https://neon.tech) and copy its connection string.
2. On [Render](https://render.com), choose **New → Blueprint** and point it at this repo — `render.yaml` provisions a free web service built from the `Dockerfile`.
3. When prompted, set `DATABASE_URL` to the Neon connection string.

Migrations run automatically on each deploy; static files are served by WhiteNoise.

## Tests

```bash
.venv/bin/python manage.py test
```
