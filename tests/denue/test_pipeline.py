from urban_denue.pipeline import STAGES, _requested


def test_stage_order_is_explicit():
    assert STAGES == ["load", "validate", "clean", "eda", "spatial", "features"]
    assert _requested("clean") == ["load", "validate", "clean"]
    assert _requested("all") == STAGES
