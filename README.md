# kl-expense

Minimal, mobile-friendly Flask app for logging personal income/expenses.
UUID-based login (no username/password), SQLite storage, SQLAlchemy ORM,
Dockerized, deployed via GHCR.

## Project layout

```
kl_expenses/
├── Dockerfile
├── lint.sh
├── pyproject.toml
├── uv.lock
├── src/
│   ├── __init__.py
│   ├── config.py        # env-sourced paths, SECRET_KEY, template/static dirs
│   ├── logger.py         # loguru setup (stderr + rotating file, no retention cap)
│   ├── wsgi.py            # gunicorn entrypoint — module-level APP
│   ├── auth.py            # current_user(), login_required decorator
│   ├── app/
│   │   ├── models.py     # User, Operation (expense/income), enums
│   │   ├── context.py    # AppContext — engine, session factory, init_app()
│   │   ├── create.py     # create_app() Flask factory
│   │   └── routes.py     # /, /login, /logout, /insert
│   ├── db/
│   │   ├── init.py       # init_db_engine(), make_session()
│   │   └── session.py    # per-request session (open_session/close_session/get_session)
│   └── cli/
│       ├── argparser.py  # argparse parser + dispatch()
│       ├── manage.py     # add/list/remove(deactivate)/restore user logic
│       └── run.py        # CLI entrypoint (python -m src.cli.run)
├── static/style.css
└── templates/{login,insert}.html

docker-compose.yml         # repo root — build context is ./kl_expenses
.env                        # not committed — see below
```

## One-time local setup

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
cd kl_expenses
uv sync                     # installs deps + dev deps into .venv
```

### `.env` file (repo root, next to `docker-compose.yml`)

```
SECRET_KEY=                 # generate below, never commit a real value
DATABASE_PATH=data/expenses.db   # MUST be relative — see Gotchas
LOG_DIR=data/logs                # MUST be relative — see Gotchas
FORCE_SECURE_COOKIE=0            # 1 once behind real HTTPS
```

Generate a secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

For running commands directly on your host (not via Docker), export the
same variables in your shell instead:
```bash
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export DATABASE_PATH=data/expenses.db
export LOG_DIR=data/logs
```

## CLI — user management

Run from inside `kl_expenses/`:

```bash
uv run python -m src.cli.run add "Alice"        # creates a user, prints their UUID login code
uv run python -m src.cli.run list                # active users only
uv run python -m src.cli.run list --all          # include deactivated
uv run python -m src.cli.run remove <uuid>       # soft-delete (deactivate) — history is kept
uv run python -m src.cli.run restore <uuid>      # reactivate
```

## Running locally without Docker

```bash
cd kl_expenses
uv run flask --app src.wsgi:APP run --debug --port 8420
```

or, closer to production (gunicorn):
```bash
uv run gunicorn --bind 0.0.0.0:8420 --workers 2 --timeout 30 src.wsgi:APP
```

Visit `http://localhost:8420`, log in with a UUID from `add` above.

To reset local state: `rm -rf kl_expenses/data` (or wherever `DATABASE_PATH`/`LOG_DIR` point).

## Running with Docker (local)

From the **repo root** (where `docker-compose.yml` lives):

```bash
docker compose build
docker compose up
```

The app is bound to `127.0.0.1:8420` only (not `0.0.0.0`) — this is
intentional, see Architecture notes below. Visit `http://localhost:8420`.

**First run on a fresh machine** — the bind-mounted `./data` directory
needs to be owned by the container's non-root user (UID/GID 999) *before*
the container starts, or you'll hit a permissions error:

```bash
mkdir -p data
sudo chown -R 999:999 data
```

Stop with `docker compose down`. Data persists in `./data` between runs
(and rebuilds) because of the bind mount.

## Linting / pre-commit

```bash
./lint.sh                        # black (writes) + ruff --fix + mypy
```

Pre-commit is configured to run the same tools automatically on every
`git commit`:
```bash
uv run pre-commit install        # one-time, per clone
```

A GitHub Actions workflow (`.github/workflows/lint.yml`) runs the
non-mutating version (`black --check`, `ruff check`, `mypy`) on every PR
into `main`, and `main` is branch-protected to require it passing before
merge (see "Branch protection" below).

## Pushing an image to GHCR (manual — until CI/CD automates this)

### One-time: authenticate Docker with a GitHub token

1. GitHub → profile photo → **Settings** → **Developer settings** →
   **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
2. Scope: `write:packages` (implies `read:packages`). Set an expiration.
3. Copy the token immediately (shown once) — save it in a password manager,
   not a plain text file.

```bash
export GH_PAT=ghp_xxxxxxxxxxxxxxxxxxxx
echo $GH_PAT | docker login ghcr.io -u tsaramaso --password-stdin
```

`docker login` persists the credential in `~/.docker/config.json` on that
machine — you don't need to repeat this per push, only per machine (or
after the token expires/is revoked).

### Tag and push

```bash
docker images | grep expense        # confirm the actual local image name/tag first
docker tag kl-expense-expense-app ghcr.io/tsaramaso/kl-expenses:latest
docker push ghcr.io/tsaramaso/kl-expenses:latest
```

Confirm it landed: `github.com/tsaramaso?tab=packages`.

### Pull on another machine (e.g. the VPS)

```bash
echo $GH_PAT | docker login ghcr.io -u tsaramaso --password-stdin   # once per machine
docker pull ghcr.io/tsaramaso/kl-expenses:latest
```

GHCR packages default to **private** — every machine pulling needs its
own authenticated login, same as above.

## Branch protection on `main`

Settings → Branches → rule for `main`:
- Require a pull request before merging
- Require status checks to pass before merging → search for the `lint`
  job name (only appears **after** the workflow has run at least once on
  a real PR — open a throwaway PR first if the search box comes up empty)
- Require branches to be up to date before merging

## Architecture notes (why things are shaped this way)

- **Auth model**: UUID-as-bearer-credential, no password. Deliberate
  simplification for a small trusted user group. Soft-delete
  (`is_active` flag) instead of hard delete, so expense history survives
  deactivating a user.
- **No hidden global state**: each real process entrypoint (`src/wsgi.py`
  for gunicorn, `src/cli/run.py` for the CLI) independently calls
  `AppContext.init_app(...)`. Neither imports the other. `src/wsgi.py`'s
  module-level `APP`/context is the one legitimate case of module-level
  state — it's the WSGI contract gunicorn requires.
- **Enums are DB-enforced** (`SAEnum` with `values_callable`) — both
  `DirectionType`/`CategoryType`/`GroupType` values are validated at the
  database level, not just in Python.
- **Docker binds to `127.0.0.1:8420` only**, not `0.0.0.0`. This VPS is
  shared with other services; nginx (not yet wired up) will be the only
  thing reachable from outside, proxying to the container over loopback.

## Known gotchas (bugs already hit once — don't re-introduce)

- **`DATABASE_PATH`/`LOG_DIR` must be relative paths** (`data/expenses.db`,
  not `/data/expenses.db`). A leading `/` makes Python's `Path` treat it
  as filesystem-root-absolute, landing outside the container's writable
  `/app/data`, and outside the volume mount entirely →
  `PermissionError: [Errno 13] Permission denied: '/data'`.
- **`mkdir` needs `parents=True`** — has regressed multiple times across
  refactors. Check `context.py`'s `init_app` if directory creation ever
  breaks again.
- **`chown -R nonroot:nonroot /app` in the Dockerfile only affects the
  image layer** — it does *not* survive a bind mount. The host's `./data`
  directory must be `chown`'d to `999:999` once, manually, on any new
  machine (see "Running with Docker" above).
- **SQLAlchemy's `Enum` type stores `.name` by default, not `.value`** —
  every `SAEnum(...)` column needs `values_callable=lambda e: [x.value for x in e]`
  explicitly, or the DB stores `INCOME` instead of the intended `income`.
- **`docker login` with a token piped via `echo` fails with "cannot
  perform an interactive login from a non-TTY device"** if the variable
  it's piping is empty — check `echo $GH_PAT` actually prints something
  before assuming Docker itself is broken.
- **Local Compose image names follow `<project-dir-name>-<service-name>`**
  — don't assume the tag; run `docker images | grep expense` to confirm
  before `docker tag`.

## Not done yet

- GitHub Actions workflow to build + push to GHCR automatically on merge
  to `main`
- VPS-side deploy step (SSH secret, `docker compose pull && up -d`)
- nginx reverse proxy config on the VPS + Cloudflare Origin Certificate
- DNS record for `expenses.fenosoa.org`