.PHONY: install dev-install test lint clean

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

test:
	pytest -v

test-coverage:
	pytest --cov=autoinfo --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/

lint-fix:
	ruff check --fix src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
