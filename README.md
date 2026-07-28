# kl-expense

Minimal, mobile-friendly Flask app for logging personal income/expenses.
UUID-based login (no username/password), SQLite storage, SQLAlchemy ORM.
Runs in Docker, built and deployed automatically via GitHub Actions to a
VPS, served over HTTPS at `https://expense.fenosoa.org`.

Built for a small group of trusted users (e.g. family). Deliberately not
hardened for scale or hostile users — see "Architecture notes" below for
what's simplified on purpose vs. what's just not done yet.

## Project layout

```
kl_expenses/
├── Dockerfile
├── lint.sh
├── pyproject.toml
├── uv.lock
├── src/
│   ├── config.py          # env-sourced paths, SECRET_KEY, template/static dirs
│   ├── logger.py          # loguru setup (stderr + rotating file, no retention cap)
│   ├── wsgi.py             # gunicorn entrypoint — module-level APP
│   ├── auth.py             # current_user(), login_required decorator
│   ├── app/
│   │   ├── models.py      # User, Operation (expense/income), enums
│   │   ├── context.py     # AppContext — engine, session factory, init_app()
│   │   ├── create.py      # create_app() Flask factory (+ ProxyFix for nginx)
│   │   └── routes.py      # /, /login, /logout, /insert
│   ├── db/
│   │   ├── init.py        # init_db_engine(), make_session()
│   │   └── session.py     # per-request session (open_session/close_session/get_session)
│   └── cli/
│       ├── argparser.py   # argparse parser + dispatch()
│       ├── manage.py      # add/list/remove(deactivate)/restore user logic
│       └── run.py         # CLI entrypoint (python -m src.cli.run)
├── static/style.css
└── templates/{login,insert}.html

kl_expenses/alembic/
├── env.py                 # target_metadata=Base.metadata, render_as_batch=True (sqlite)
└── versions/              # migration scripts — `baseline` stamps the redesigned schema

docker-compose.yml          # repo root — image: ghcr.io/tsaramaso/kl-expenses:latest
.github/workflows/
├── deploy.yml              # build + push to GHCR, then deploy to VPS
└── lint.yml                # black/ruff/mypy check on every PR into main
.env                         # not committed — see below
```

## Collaborating / opening a PR

1. Branch off `main`, make changes inside `kl_expenses/`.
2. Run `./lint.sh` before pushing (see "Linting" below) — the same checks
   run in CI and **must pass before merge is allowed** (branch protection
   on `main`, see "GitHub side" below).
3. Open a PR into `main`. `lint.yml` runs automatically.
4. Merging into `main` **automatically builds and deploys to production**
   — there is no staging environment. Treat a merge as "this goes live."

## Local development setup

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
cd kl_expenses
uv sync                     # installs deps + dev deps into .venv
```

### `.env` file (repo root, next to `docker-compose.yml`, never committed)

```
SECRET_KEY=                      # generate below
DATABASE_PATH=data/expenses.db   # MUST be relative — see Gotchas
LOG_DIR=data/logs                # MUST be relative — see Gotchas
FORCE_SECURE_COOKIE=0            # 1 only when served over real HTTPS
```

Generate a secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Running commands directly on your host instead of via Docker? Export the
same variables in your shell instead of using `.env`:
```bash
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export DATABASE_PATH=data/expenses.db
export LOG_DIR=data/logs
```

Schema is Alembic-owned — `init_db_engine()` no longer calls
`create_all()`, so a fresh clone has **no tables at all** until you run
migrations:

```bash
cd kl_expenses
uv run alembic upgrade head    # required before first run, and after pulling any migration
```

### Running locally without Docker

```bash
cd kl_expenses
uv run flask --app src.wsgi:APP run --debug --port 8420
```

or, closer to production (gunicorn):
```bash
uv run gunicorn --bind 0.0.0.0:8420 --workers 2 --timeout 30 src.wsgi:APP
```

Visit `http://localhost:8420`. To reset local state: `rm -rf kl_expenses/data`
(or wherever `DATABASE_PATH`/`LOG_DIR` point).

### Running with Docker (local)

From the **repo root** (where `docker-compose.yml` lives). Local testing
should build from source, not pull the production image — temporarily
edit the `expense-app` service in `docker-compose.yml` to use `build: ./kl_expenses`
instead of `image: ghcr.io/...` (don't commit that change):

```bash
mkdir -p data
sudo chown -R 999:999 data   # container runs as non-root UID/GID 999
docker compose build
docker compose run --rm expense-app uv run alembic upgrade head   # required — no create_all() anymore
docker compose up
```

Visit `http://localhost:8420`. Stop with `docker compose down`; data
persists in `./data` between runs because of the bind mount.

### Linting

```bash
./lint.sh                        # black (writes) + ruff --fix + mypy
```

One-time per clone, to run the same checks automatically on every commit:
```bash
uv run pre-commit install
```

## Admin — managing users (UUID login codes)

There's no web UI for this by design — matches the CLI-only auth model.
Every action below needs shell access (locally, or SSH'd into the VPS).

**Locally** (from inside `kl_expenses/`):
```bash
uv run python -m src.cli.run add "Alice"     # creates a user, prints their UUID login code
uv run python -m src.cli.run list             # active users only
uv run python -m src.cli.run list --all       # include deactivated
uv run python -m src.cli.run remove <uuid>    # soft-delete (deactivate) — history is kept
uv run python -m src.cli.run restore <uuid>   # reactivate
```

**On production** — SSH into the VPS, then run the same commands inside
the already-running container via `docker exec`:
```bash
docker exec -it expense-app uv run python -m src.cli.run add "Alice"
docker exec -it expense-app uv run python -m src.cli.run list
docker exec -it expense-app uv run python -m src.cli.run remove <uuid>
docker exec -it expense-app uv run python -m src.cli.run restore <uuid>
```
This is safe to run any time, including while the app is serving live
traffic — it writes to the same SQLite file the web app uses, via the
bind-mounted `/opt/kl-expenses/data` volume, which survives container
restarts and redeploys.

## Schema & migrations

`Operation` records one income or expense row per user. Three enums,
each an independent dimension (deliberately not overlapping):

- `DirectionType` — `INCOME` / `EXPENSE`
- `CategoryType` — `KL` / `HOME` / `USER` / `OTHER` — who/what it's for
- `ExpenseType` — `GROCERIES`, `UTILITIES`, `OTHER`, `MATERIAL`, `FOOD`,
  `RENT`, `BILL`, `SALARY`, `PERSONAL`, `FUEL` — nullable, only
  meaningful when `direction=EXPENSE`

`Operation` also has `related_user_uuid` — a second, independent FK to
`users.uuid`, nullable. Distinct from `user_uuid` (who logged the entry):
this is who the entry is *for* (self or one of the other users).

This replaced an earlier `group` + `category` design that conflated "who
paid" with "what it was spent on." Migrating the live data wasn't a
mechanical column rename — see the schema history in git for how the old
rows were remapped.

**Schema changes go through Alembic**, not hand-edited SQL:
```bash
cd kl_expenses
uv run alembic revision --autogenerate -m "short description"
# review the generated file carefully, especially renames and new
# NOT NULL columns — autogenerate doesn't always get intent right
uv run alembic upgrade head
```
`alembic/env.py` sets `render_as_batch=True` on both the offline and
online configure calls — required, because SQLite can't do most
`ALTER TABLE` forms directly; Alembic instead rebuilds the table under
the hood via a temp-table swap.

**Two FKs from `Operation` to `users.uuid`** (`user_uuid` and
`related_user_uuid`) means both `Operation.user` and `User.expenses`
need an explicit `foreign_keys=` argument on their `relationship()` —
leaving either one off raises `AmbiguousForeignKeysError` at import
time, since SQLAlchemy can't infer which FK each relationship means.

## What's done — GitHub side

- **Repo secrets** (Settings → Secrets and variables → Actions):
  - `VPS_SSH_KEY` — private half of a dedicated deploy-only keypair
    (not anyone's personal SSH key)
  - `VPS_HOST` — the VPS's public IP
- **`.github/workflows/deploy.yml`** — triggers on push to `main` and via
  manual `workflow_dispatch` (a "Run workflow" button on the Actions tab).
  Two jobs:
  1. `build-and-push` — builds the Docker image from `kl_expenses/`,
     pushes `ghcr.io/tsaramaso/kl-expenses:latest` and `:<commit-sha>`
     to GitHub Container Registry, using the automatic `GITHUB_TOKEN`
     (no PAT needed for this part).
  2. `deploy` (needs `build-and-push`) — scp's the repo's
     `docker-compose.yml` to `/opt/kl-expenses/` on the VPS, then three
     separate SSH steps (not chained with `&&`, so a failure at any
     stage stops the pipeline cleanly instead of limping forward):
     1. `docker compose pull`
     2. `docker compose run --rm expense-app uv run alembic upgrade head`
        — a throwaway container, not `exec` into the running one; right
        after `pull`, the *running* container is still on the old image
     3. `docker compose up -d`
- **`.github/workflows/lint.yml`** — runs `black --check`, `ruff check`,
  `mypy` on every PR into `main`.
- **Branch protection on `main`** (Settings → Branches): PR required,
  the `lint` status check required to pass, branch must be up to date
  before merge.
- **GHCR package visibility: public.** Deliberate for this project — low
  stakes, no secrets baked into the image (those live only in the VPS's
  `.env`), and it means the VPS never needs its own registry credentials
  to pull. Not the right default for a more sensitive app — see
  "Architecture notes" for the private-package alternative.

## What's done — VPS side

- **Dedicated `deploy` unix user**, member of the `docker` group only
  (not root, not sudo). Login is SSH-key-only — `adduser --disabled-password`,
  so no password login exists for this account at all.
- **Dedicated SSH keypair** for GitHub Actions, public half in
  `/home/deploy/.ssh/authorized_keys` — not the same key as anyone's
  personal SSH access to the box.
- **`/opt/kl-expenses/`** — the deploy target directory:
  - `docker-compose.yml` — overwritten automatically by CI on every
    deploy, never hand-edited
  - `.env` — hand-created once, holds `SECRET_KEY`, `DATABASE_PATH`,
    `LOG_DIR`, `FORCE_SECURE_COOKIE` — deliberately outside git, CI never
    touches it
  - `data/` — bind-mounted into the container at `/app/data`; holds
    `expenses.db` and `logs/`. **Must be owned by UID/GID `999:999`**
    (the container's non-root user), not by `deploy` — see Gotchas.
- **nginx** reverse-proxies `expense.fenosoa.org` (port 80/443) to the
  container's `127.0.0.1:8420` (loopback-only — the app is not reachable
  directly from outside the VPS). Config at
  `/etc/nginx/sites-available/expense.fenosoa.org`.
- **TLS via Let's Encrypt / certbot** (`certbot --nginx -d expense.fenosoa.org`)
  — certbot edited the nginx config in place to add the `listen 443 ssl`
  block and an automatic HTTP→HTTPS redirect. Renewal is automatic via a
  systemd timer certbot installs — nothing to do manually going forward
  unless the domain or nginx config changes structurally.
- **DNS**: `expense.fenosoa.org` A record in Cloudflare, proxy status set
  to **Proxied (orange cloud)**. SSL/TLS mode set to **Full (strict)** —
  requires the origin to present a real, valid certificate (which it does,
  via certbot), so the whole path browser→Cloudflare→VPS stays encrypted.
  (Briefly set to DNS-only/grey while certbot's HTTP-01 challenge needed
  to reach the VPS directly — switched to Proxied only after the cert was
  issued.)
- **Origin lockdown**: nginx's `expense.fenosoa.org` HTTPS server block
  has an `allow`/`deny` list restricting it to Cloudflare's published IP
  ranges only (https://www.cloudflare.com/ips-v4, `-v6`) — anyone hitting
  the VPS's raw IP directly, or forging the `Host` header to bypass
  Cloudflare's DNS, gets a 403 at the nginx level, never reaching Flask.
  Scoped to *this app's* server block specifically — other services on
  the same VPS, in their own server blocks, are unaffected.
- **`FORCE_SECURE_COOKIE=1`** in `.env`, container restarted after — the
  session cookie now requires HTTPS. `ProxyFix` in `src/app/create.py`
  is what lets Flask correctly detect the connection as secure despite
  gunicorn itself only ever seeing plain HTTP from nginx.

## Architecture notes (why things are shaped this way)

- **Auth model**: UUID-as-bearer-credential, no password. Deliberate
  simplification for a small trusted user group. Soft-delete
  (`is_active` flag) instead of hard delete, so expense history survives
  deactivating a user. No PIN, no rate-limiting — known, deliberately
  deferred, not oversights.
- **No hidden global state**: each real process entrypoint (`src/wsgi.py`
  for gunicorn, `src/cli/run.py` for the CLI) independently calls
  `AppContext.init_app(...)`. Neither imports the other. `src/wsgi.py`'s
  module-level `APP`/context is the one legitimate case of module-level
  state — it's the WSGI contract gunicorn requires.
- **Enums are DB-enforced** (`SAEnum` with `values_callable`) —
  `DirectionType`/`CategoryType`/`ExpenseType` values are validated at the
  database level, not just in Python.
- **Docker binds to `127.0.0.1:8420` only**, not `0.0.0.0` — nginx is the
  only thing reachable from outside the VPS, proxying over loopback.
- **No CSRF token on the login/insert forms** — consistent with the
  "not hardened, low-stakes" brief. A real gap, not an oversight; would
  need `flask-wtf` or equivalent if this app's stakes ever change.
- **GHCR package is public** — fine here since the image has no secrets
  in it. For a higher-stakes app: keep the package private, generate a
  fine-grained PAT with only `read:packages`, and `docker login` once on
  the VPS with it (`echo $PAT | docker login ghcr.io -u <user> --password-stdin`) —
  credentials are cached in `deploy`'s `~/.docker/config.json`, so this is
  a one-time step per machine, not per deploy.

## Known gotchas (bugs already hit once — don't re-introduce)

- **`DATABASE_PATH`/`LOG_DIR` must be relative paths** (`data/expenses.db`,
  not `/data/expenses.db`). A leading `/` makes Python's `Path` treat it
  as filesystem-root-absolute, landing outside the container's writable
  `/app/data` entirely → `PermissionError`.
- **`mkdir` needs `parents=True`** — has regressed multiple times across
  refactors. Check `context.py`'s `init_app` if directory creation ever
  breaks again.
- **Bind-mounted `data/` ownership must match the container's UID (999),
  not the host's `deploy` user.** `chown -R nonroot:nonroot /app` in the
  Dockerfile only affects the image layer — it does not affect a bind
  mount. On a fresh VPS or fresh clone: `chown -R 999:999 data` on the
  host, always, or the app crashes on boot trying to create `data/logs`.
- **SQLAlchemy's `Enum` type stores `.name` by default, not `.value`** —
  every `SAEnum(...)` column needs
  `values_callable=lambda e: [x.value for x in e]` explicitly, or the DB
  stores `INCOME` instead of the intended `income`.
- **Missing `VPS_HOST` or `VPS_SSH_KEY` secrets fail silently at the
  `on:`/`secrets.` reference level** — GitHub doesn't error on a
  referenced-but-unset secret, it just resolves to an empty string. If
  the `deploy` job fails to connect, check both secrets actually exist
  before debugging anything else.
- **A GHCR package created by a manual local `docker push` is *not*
  automatically linked to the repo** — GitHub Actions' `GITHUB_TOKEN` is
  scoped per-repo and won't have write access to a package it doesn't
  recognize as connected. Fix once, per package: package's own Settings
  → **Manage Actions access** → add the repo, role Write.
- **Cloudflare DNS records default to "Proxied" (orange cloud)** — must
  be switched to "DNS only" (grey cloud) temporarily during certbot's
  initial HTTP-01 challenge, then can be switched back to Proxied once
  the cert is issued.
- **Testing "does the origin lockdown actually work" needs the right
  command** — `curl https://<vps-ip>/` fails on a cert name mismatch
  (expected — the cert is only valid for the domain, not the IP) and
  tells you nothing about the `allow`/`deny` rule. A bare-IP *HTTP*
  request also tells you nothing — it hits nginx's unrelated
  `default_server` block (the stock "Welcome to nginx!" page), not your
  app's server block at all. The real test forges the domain via SNI
  while still connecting to the raw IP:
  `curl -i https://expense.fenosoa.org/ --resolve expense.fenosoa.org:443:<vps-ip>`
  — this should return `403 Forbidden` if the lockdown is working.
- **CI/CD jobs share nothing by default** — each job in a workflow is a
  fresh runner with an empty filesystem. Any job that needs repo files
  (e.g. to scp `docker-compose.yml`) needs its own `actions/checkout`
  step, even if an earlier job already checked out the same repo.
- **SQLAlchemy's `SAEnum` on SQLite does not generate a `CHECK`
  constraint by default** — `create_constraint` has defaulted to `False`
  for non-native enum types since SQLAlchemy 1.4. The real (small)
  residual risk is a Python-side `LookupError` on read if an enum member
  is removed/renamed while old rows still hold it — purely additive
  enum changes are free.
- **`sudo` doesn't inherit the calling shell's `PATH`** — `sudo uv run
  ...` fails with `command not found` even when `uv` works fine
  unprivileged. Don't chase `sudo` for a `uv`/venv-based command; fix
  the actual permission/ownership problem on the directory instead.
  `chmod 777` "fixes" it too, but isn't the correct fix — `chown` to the
  right user, keep permissions at `755` or tighter.
- **Manual file transfers to the VPS need a re-`chown`** — `scp` writes
  as the connecting user (`deploy`), not `999`. After copying anything
  into `data/` by hand (e.g. swapping in a rebuilt sqlite file), `chown
  999:999` it again or the container can't write to it.
- **Host and container UID/GID numbers matching is what matters** for
  bind-mount permissions — the *name* attached to that number (e.g. some
  unrelated system group happening to also be GID 999 on the host) is
  irrelevant; container and host have separate `/etc/group` tables, only
  the numeric ID crosses the bind-mount boundary.

## Not done yet

- Web-based admin UI (currently CLI/SSH-only, deliberately)
- Rate-limiting / PIN on login (known deferred item from the original
  auth-model decision)