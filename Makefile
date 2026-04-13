.PHONY: lint fix test

# Run the full quality gate in order: fast linting → formatting check → types → security
lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
	.venv/bin/mypy .
	.venv/bin/bandit -r . -c pyproject.toml -x .venv

# Auto-fix everything ruff can fix, then reformat
fix:
	.venv/bin/ruff check --fix .
	.venv/bin/ruff format .

# Full test suite
test:
	.venv/bin/python3 -m pytest tests/ -v
