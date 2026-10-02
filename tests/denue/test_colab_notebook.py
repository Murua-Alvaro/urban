from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK = Path("notebooks/denue/00_COLAB_START_HERE.ipynb")
ENTRYPOINT = Path("scripts/denue/colab_entrypoint.py")


def _notebook() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def test_start_here_notebook_is_valid_nbformat4_json() -> None:
    notebook = _notebook()
    assert notebook["nbformat"] == 4
    assert isinstance(notebook.get("cells"), list)
    assert notebook["cells"]


def test_every_python_cell_compiles() -> None:
    notebook = _notebook()
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        compile(source, f"{NOTEBOOK}:cell-{index}", "exec")


def test_notebook_uses_direct_pipeline_api() -> None:
    notebook = _notebook()
    source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    assert "from urban_denue.pipeline import run_pipeline" in source
    assert "run_pipeline(" in source
    assert "scripts/denue/colab_entrypoint.py" not in source
    assert "2_889_999" in source
    assert "138_882" in source
    assert "27_487" in source


def test_colab_entrypoint_does_not_wrap_pipeline_in_subprocess() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    assert "from urban_denue.pipeline import run_pipeline" in source
    assert "subprocess.run" not in source
    assert "subprocess.call" not in source
