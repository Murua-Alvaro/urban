PYTHON ?= python
ROOT ?= var/denue

.PHONY: install test denue-load denue-validate denue-clean denue-eda denue-spatial denue-features denue-all denue-report denue-model denue-full

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	ruff check src tests scripts
	pytest -q

denue-load:
	$(PYTHON) scripts/denue/run_pipeline.py --root $(ROOT) --through load

denue-validate:
	$(PYTHON) scripts/denue/run_pipeline.py --root $(ROOT) --through validate

denue-clean:
	$(PYTHON) scripts/denue/run_pipeline.py --root $(ROOT) --through clean

denue-eda:
	$(PYTHON) scripts/denue/run_pipeline.py --root $(ROOT) --through eda

denue-spatial:
	$(PYTHON) scripts/denue/run_pipeline.py --root $(ROOT) --through spatial

denue-features:
	$(PYTHON) scripts/denue/run_pipeline.py --root $(ROOT) --through features

denue-all:
	$(PYTHON) scripts/denue/run_pipeline.py --root $(ROOT) --through all

denue-report: denue-all
	$(PYTHON) scripts/denue/report.py --root $(ROOT) --municipality 012

denue-model: denue-all
	$(PYTHON) scripts/denue/model.py --root $(ROOT)

denue-full: denue-all
	$(PYTHON) scripts/denue/report.py --root $(ROOT) --municipality 012
	$(PYTHON) scripts/denue/model.py --root $(ROOT)
