import json
from pathlib import Path

from urban_denue.validation import validate_extracted


def test_core_and_territorial_crosschecks(tmp_path: Path):
    root = tmp_path / "data"
    (root / "ediciones").mkdir(parents=True)
    municipalities = {"25_012": {"name":"Mazatlan", "history_totals": {}}}
    state_totals = {}
    territorial = {"editions": [], "municipalities": {"25_012": {"ageb":{}, "grid":{}}}}
    fields = ["ageb", "grid", "sector", "size", "class", "cp", "flags", "n"]
    territorial["municipalities"]["25_012"]["ageb"]["a"] = [2] * 25
    territorial["municipalities"]["25_012"]["grid"]["g"] = [2] * 25
    for i in range(25):
        label = f"e{i:02d}"
        municipalities["25_012"]["history_totals"][label] = 2
        state_totals[label] = 2
        territorial["editions"].append(label)
        payload = {"25_012": {"fields": fields, "rows": [["a","g","11",1,"112511","82000",1,2]], "total":2}}
        (root / "ediciones" / f"{label}.json").write_text(json.dumps(payload), encoding="utf-8")
    core = {"manifest":{"municipalities":municipalities}, "stateTotals":state_totals, "summaries":{}, "activities":{"112511":"x"}}
    (root / "core.json").write_text(json.dumps(core), encoding="utf-8")
    (root / "historico_territorial.json").write_text(json.dumps(territorial), encoding="utf-8")
    report = validate_extracted(tmp_path)
    assert not report.errors
    assert report.core_total_checks == 50
    assert report.territorial_checks == 50
