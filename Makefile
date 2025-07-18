install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.6.12/install.sh | sh; source $HOME/.local/bin/env; }
	uv sync
	(cd langgraph_backend && uv sync)
	npm --prefix frontend install

dev:
	make dev-backend & make dev-frontend

dev-backend:
	@echo "Starting backend server..."
	cd langgraph_backend && BG_JOB_ISOLATED_LOOPS=true uv run langgraph dev --allow-blocking

dev-frontend:
	@echo "Starting frontend server..."
	npm --prefix frontend run dev

playground:
	uv run adk web --port 8501

lint:
	uv run codespell
	uv run ruff check . --diff
	uv run ruff format . --check --diff
	uv run mypy .
