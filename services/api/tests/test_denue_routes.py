from __future__ import annotations

from fastapi.testclient import TestClient

from app import denue_routes
from app.main import app

client = TestClient(app)


def test_municipality_code_is_validated() -> None:
    response = client.get("/v1/denue/municipalities/not-a-code/timeseries")
    assert response.status_code == 422


def test_timeseries_returns_repository_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        denue_routes,
        "municipality_timeseries",
        lambda code: [
            {
                "source_edition": "2026-05",
                "edition_date": "2026-05-01",
                "is_rebenchmark": False,
                "establishments": 27487,
                "active_agebs": 309,
                "active_grids": 191,
            }
        ],
    )
    response = client.get("/v1/denue/municipalities/25_012/timeseries")
    assert response.status_code == 200
    body = response.json()
    assert body["municipality_code"] == "25_012"
    assert body["observations"][0]["establishments"] == 27487


def test_empty_timeseries_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(denue_routes, "municipality_timeseries", lambda code: [])
    response = client.get("/v1/denue/municipalities/25_012/timeseries")
    assert response.status_code == 404


def test_sector_endpoint_requires_edition() -> None:
    response = client.get("/v1/denue/municipalities/25_012/sectors")
    assert response.status_code == 422


def test_grid_endpoint_returns_feature_collection(monkeypatch) -> None:
    monkeypatch.setattr(
        denue_routes,
        "municipality_grids",
        lambda municipality_code, source_edition, min_establishments=0: {
            "type": "FeatureCollection",
            "municipality_code": municipality_code,
            "source_edition": source_edition,
            "features": [
                {
                    "type": "Feature",
                    "id": "25_012|g1",
                    "geometry": {"type": "Polygon", "coordinates": []},
                    "properties": {"grid_id": "g1", "establishments": 10},
                }
            ],
        },
    )
    response = client.get("/v1/denue/municipalities/25_012/grids?edition=2026-05")
    assert response.status_code == 200
    assert response.json()["features"][0]["properties"]["establishments"] == 10
