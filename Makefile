requirements.txt: requirements.in .tool-versions
	uv pip compile requirements.in -o requirements.txt --no-strip-extras

.venv/bin/activate:
	uv venv --python 3.12

sync: requirements.txt .venv/bin/activate
	uv pip sync requirements.txt

test: sync
	uv run pytest -vvv
