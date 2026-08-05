.PHONY: install dev-install test lint clean stripe-mock backup

install:
	pip install -e .

dev-install:
	# For full coverage (pytest-cov + the optional deps the HAVE_* gates in
	# tests/conftest.py guard): pip install -e ".[dev,stripe,pdf,tts,web,video]"
	# Note: stripe is a core dependency (always pulled in); web/pdf/tts/video are
	# extras and ffmpeg must be on PATH separately. `pip install -e ".[all]"` also works.
	pip install -e ".[dev]"

test:
	pytest -v

test-coverage:
	# Requires pytest-cov (in the dev extra). Run with optional extras installed
	# (see dev-install) for full coverage of the HAVE_*-gated modules.
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

stripe-mock:
	docker compose up -d stripe-mock

backup:
	bash scripts/backup-db.sh
