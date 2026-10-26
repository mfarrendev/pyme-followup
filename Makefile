.PHONY: setup test lint demo run trabajador clean

RUN = PYTHONPATH=. uv run

setup:
	uv sync

test:
	$(RUN) pytest tests -v

lint:
	uv run ruff check app tests scripts
	uv run ruff format --check app tests scripts

# Carga datos de demostración (imprime la clave del panel).
# El servidor se crea con --factory: importar app.web no abre ni crea la base.
demo:
	$(RUN) python -m scripts.cargar_demo

run:
	$(RUN) uvicorn --factory app.web:crear_app --reload --port 8000

# En producción, esto va en cron cada 5 minutos.
trabajador:
	$(RUN) python -m app.trabajador

clean:
	rm -rf datos
