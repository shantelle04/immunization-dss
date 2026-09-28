# 08. Setup and git

## 1. Repository configuration

| Item | State |
|---|---|
| Repository | GitHub `shantelle04/immunization-dss` (private), branch `main` |
| SSH | Repository-local `core.sshCommand` using a dedicated ed25519 key for this project (key file `id_ed25519_168873` in the user's SSH folder); GitHub authentication confirmed 2026-09-28 |
| Identity | `user.useConfigOnly = true`; repository-local `user.name = shantelle04` and `user.email`; the machine's global identity is never used |
| Remote | `origin = git@github.com:shantelle04/immunization-dss.git`; `guard.githubOwner = shantelle04` |
| Hooks | Versioned in `scripts/hooks/`, enabled by `core.hooksPath` (set by `dev.py setup`). `pre-commit` refuses staged files that match any ignore rule (even if force-added) and files containing machine-specific paths. `pre-push` allows only `guard.githubOwner` over SSH and refuses tracked files that match ignore rules or contain machine paths |
| Committed | Code, tests, configuration, `data/README.md`, and the project notes in `docs/` (D-28) |
| Not committed | Secrets (`.env`, keys), generated data (`data/*`), trained models, copies of third-party reference documents (`docs/reference/`), review files (`pr_*.md`), progress-report exports, and local tool files listed in the repository-local exclude file |

## 2. Setting up a machine (once per machine)

```bash
# 1. Dedicated SSH key for this project, added to the shantelle04 GitHub account
#    (Settings > SSH and GPG keys > New SSH key)
ssh-keygen -t ed25519 -C "shantelle04 immunization-dss" -f <ssh-folder>/id_ed25519_168873

# 2. Clone with that key
git clone -c core.sshCommand="ssh -i <ssh-folder>/id_ed25519_168873 -o IdentitiesOnly=yes" \
  git@github.com:shantelle04/immunization-dss.git
cd immunization-dss

# 3. Repository-local identity and push guard
git config --local user.useConfigOnly true
git config --local user.name shantelle04
git config --local user.email "<GitHub email or noreply address>"
git config --local guard.githubOwner shantelle04

# 4. Test the key
ssh -i <ssh-folder>/id_ed25519_168873 -o IdentitiesOnly=yes -T git@github.com

# 5. Tools, hooks, environment, database, data
python3 scripts/dev.py setup        # also enables scripts/hooks
python3 scripts/dev.py bootstrap
python3 scripts/dev.py simulate
```

`<ssh-folder>` is the user's SSH directory (usually `.ssh` in the home folder). Then restore the local-only files (reference PDFs, local exclude list, assistant files) from the personal backup (section 5).

## 3. Machine prerequisites

| Tool | Development machine (2026-09-28) | Needed |
|---|---|---|
| Python | 3.12.3 | 3.12 with `venv` |
| Node | 22.18.0 | 20 or 22 |
| Docker | 29.1.3, Compose 2.40.3 | Required (D-20) |
| Git | 2.43.0 | Any recent |

PostgreSQL (D-20) runs in Docker via `docker-compose.yml` on `127.0.0.1:5433` (5432 was already in use on the development machine). On first start, `backend/docker/initdb/01-roles.sh` creates two roles from `.env`: `DB_USER` (application, owns `DB_NAME`) and `DB_TEST_USER` (tests, `CREATEDB`). It refuses placeholder or short passwords and a shared role.

## 4. Quick start (Linux and Windows)

```bash
python3 scripts/dev.py setup      # Windows: py scripts\dev.py setup
python3 scripts/dev.py env        # generates .env with random secrets (never overwrites, prints no values)
python3 scripts/dev.py db-up      # PostgreSQL 16 in Docker, waits until healthy
python3 scripts/dev.py check      # Django starts only with valid settings
python3 scripts/dev.py test       # analytics, scripts, backend, frontend
```

`db-reset` deletes the database volume (asks first); needed if the roles must be re-created, because the init script runs only on an empty volume.

## 5. Backup of local-only files

`docs/` is now in the repository. The files that stay local (reference PDFs in `docs/reference/`, the repository-local exclude list, and local tool files) should be archived weekly to personal cloud storage, for example from the repository folder:

```bash
tar czf ../immunization-dss-local-$(date +%F).tgz docs/reference .git/info/exclude
```

Add any other local-only files you keep in the repository folder to that command.
