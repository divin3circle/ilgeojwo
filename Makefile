PORT ?= 8000

.PHONY: run test setup
setup:
	./setup.sh

test:
	uv run pytest -v

golden:
	uv run pytest tests/golden -m slow -v

run:
	@ILGEOJWO_PORT=$(PORT) uv run python -m ilgeojwo.serve
