# NAS Web Server

Web-based interface for managing a Network Attached Storage (NAS) server.

## Setup

### Development

1. Clone the repo
2. Create a virtual environment: `python3 -m venv .venv`
3. Activate it: `source .venv/bin/activate`
4. Install dev dependencies: `pip install -r requirements-dev.txt`
5. Run the server: `NAS_STORAGE=./storage NAS_BACKUPS=./backups python3 app.py`
6. Open `http://localhost:5000` — login with `admin` / `admin`

### Production (Ubuntu VM)

1. Clone the repo
2. Create a virtual environment: `python3 -m venv .venv`
3. Activate it: `source .venv/bin/activate`
4. Install production dependencies: `pip install -r requirements.txt`
5. Create storage directories: `sudo mkdir -p /srv/nas /srv/nas-backups && sudo chown $USER:$USER /srv/nas /srv/nas-backups`
6. Set a strong secret key: `export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")`
7. Run the server: `python3 app.py`
8. Open `http://localhost:5000` — login with `admin` / `admin`

## Environment Variables

<!-- AUTO-GENERATED from config.py -->
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | No | `dev-secret-key-change-in-production` | Flask session signing key — set a strong random value in production |
| `NAS_STORAGE` | No | `/srv/nas` | Absolute path to the file storage root |
| `NAS_BACKUPS` | No | `/srv/nas-backups` | Absolute path to the backup archive directory |
<!-- END AUTO-GENERATED -->

## Commands

<!-- AUTO-GENERATED from Makefile -->
| Command | Description |
|---------|-------------|
| `NAS_STORAGE=./storage NAS_BACKUPS=./backups python3 app.py` | Start the dev server (local storage dirs) |
| `python3 app.py` | Start the server in production (uses `/srv/nas` and `/srv/nas-backups`) |
| `make test` | Run the full test suite |
| `make coverage` | Run tests with coverage report (requires 80% minimum) |
| `make lint` | Run ruff, mypy, bandit, and vulture in sequence |
| `make fix` | Auto-fix ruff issues and reformat code |
| `make dead-code` | Check for unused code with vulture |
<!-- END AUTO-GENERATED -->

## Team Modules

| Module | Blueprint | Templates | Owner |
|--------|-----------|-----------|-------|
| User Management | `blueprints/auth.py`, `blueprints/users.py` | `templates/users/` | Ben Blake |
| File Management | `blueprints/files.py` | `templates/files/` | Rasagyna Peddapalli |
| System Monitoring | `blueprints/monitor.py` | `templates/monitor/` | Bhavya Harshitha Chennu |
| Backup & Restore | `blueprints/backup.py` | `templates/backup/` | Mukunda Chakravartula |

## Routes

<!-- AUTO-GENERATED from blueprints/ -->
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET/POST | `/login` | — | Login page |
| GET | `/logout` | login | End session |
| GET | `/` | login | Dashboard |
| GET | `/users/` | admin | List all users |
| GET/POST | `/users/create` | admin | Create a new user |
| GET/POST | `/users/<id>/edit` | admin | Edit a user |
| POST | `/users/<id>/delete` | admin | Delete a user |
| GET/POST | `/users/profile` | login | Change own password |
| GET | `/files/` | login | Browse files |
| GET | `/files/download` | login | Download a file |
| POST | `/files/upload` | write | Upload a file |
| POST | `/files/mkdir` | write | Create a directory |
| POST | `/files/rename` | write | Rename a file or directory |
| POST | `/files/delete` | write | Delete a file or directory |
| GET | `/monitor/` | login | System stats dashboard |
| GET | `/monitor/logs` | login | View system logs |
| GET | `/backup/` | admin | List backups |
| POST | `/backup/create` | admin | Create a backup |
| GET/POST | `/backup/schedule` | admin | Configure scheduled backups |
| POST | `/backup/restore/<id>` | admin | Restore from a backup |
| POST | `/backup/<id>/delete` | admin | Delete a backup |
<!-- END AUTO-GENERATED -->

Auth column: `—` = public, `login` = any authenticated user, `write` = users with write permission, `admin` = admins only.

## How to Work on Your Module

1. Pull the latest `main` branch
2. Create a feature branch: `git checkout -b feature/your-module`
3. Edit your blueprint in `blueprints/your_module.py`
4. Edit your templates in `templates/your_module/`
5. Use `@login_required`, `@admin_required`, or `@permission_required('write')` from `utils.decorators`
6. Run tests: `make test`
7. Push and open a pull request

## Running Tests

```bash
# Run tests
make test

# Run tests with coverage report
make coverage
```
