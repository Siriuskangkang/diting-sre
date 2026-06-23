.PHONY: install ingest rag agent ui eval mcp test lint clean

install:
	pip install -r requirements.txt
	cp -n .env.example .env || true

ingest:
	python scripts/ingest.py --reset

rag:
	python scripts/demo_rag.py

agent:
	python scripts/demo_agent.py

ui:
	python -m opscopilot.ui.app

eval:
	python scripts/eval_rag.py

mcp:
	python mcp/run_github_server.py

mcp-dev:
	mcp dev mcp/run_github_server.py

test:
	pytest

lint:
	ruff check src tests scripts

clean:
	rm -rf .chroma data/eval/results __pycache__ .pytest_cache .ruff_cache
