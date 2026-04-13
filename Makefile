.PHONY: lint fix test dead-code

# Run the full quality gate in order: fast linting → formatting check → types → security → dead code
lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
	.venv/bin/mypy .
	.venv/bin/bandit -r . -c pyproject.toml -x .venv
	.venv/bin/vulture . --exclude .venv --min-confidence 80

# Check for dead code
dead-code:
	.venv/bin/vulture . --exclude .venv --min-confidence 80

# Auto-fix everything ruff can fix, then reformat
fix:
	.venv/bin/ruff check --fix .
	.venv/bin/ruff format .

# Full test suite
test:
	.venv/bin/python3 -m pytest tests/ -v
