.PHONY: install-dev test lint format run

install-dev:
	pip install -r requirements-dev.txt

test:
	pytest -q

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check . --fix

run:
	python app.py
