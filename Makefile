PORT ?= 8000

.PHONY: run test setup
setup:
	./setup.sh

test:
	uv run pytest -v

run:
	@uv run python -c "from ilgeojwo.lan import lan_url, print_qr; print_qr(lan_url($(PORT)))"
	@uv run uvicorn --factory ilgeojwo.web.wire:app --host 0.0.0.0 --port $(PORT)
