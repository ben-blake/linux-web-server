# NAS Web Server

Web-based interface for managing a Network Attached Storage (NAS) server.

## Setup

1. Clone the repo
2. Create a virtual environment: `python3 -m venv .venv`
3. Activate it: `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the server: `python3 app.py`
6. Open `http://localhost:5000` — login with `admin` / `admin`

## Team Modules

| Module | Blueprint | Templates | Owner |
|--------|-----------|-----------|-------|
| User Management | `blueprints/auth.py`, `blueprints/users.py` | `templates/users/` | Ben Blake <ben.blake@umkc.edu>|
| File Management | `blueprints/files.py` | `templates/files/` | TBD |
| System Monitoring | `blueprints/monitor.py` | `templates/monitor/` | TBD |
| Backup & Restore | `blueprints/backup.py` | `templates/backup/` | TBD |

## How to Work on Your Module

1. Pull the latest `main` branch
2. Create a feature branch: `git checkout -b feature/your-module`
3. Edit your blueprint in `blueprints/your_module.py`
4. Edit your templates in `templates/your_module/`
5. Use `@login_required`, `@admin_required`, or `@permission_required('write')` from `utils.decorators`
6. Run tests: `python3 -m pytest tests/ -v`
7. Push and open a pull request

## Running Tests

```bash
python3 -m pytest tests/ -v
```
