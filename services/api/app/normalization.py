from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from .config import settings
from .db import engine


ALIASES: dict[str, tuple[str, ...]] = {
    "external_id": ("external_id", "id", "id_propiedad", "property_id", "listing_id", "clave"),
    "address": ("address", "direccion", "domicilio", "calle"),
    "neighborhood": ("neighborhood", "colonia", "fraccionamiento", "barrio", "zona"),
    "property_type": ("property_type", "tipo_propiedad", "tipo", "inmueble"),
    "listing_type": ("listing_type", "tipo_operacion", "operacion", "venta_renta"),
    "price": ("price", "precio", "precio_mxn", "valor", "importe"),
    "area_land_m2": ("area_land_m2", "terreno_m2", "superficie_terreno", "area_terreno", "land_area"),
    "area_built_m2": (
        "area_built_m2",
        "construccion_m2",
        "superficie_construccion",
        "area_construida",
        "built_area",
    ),
    "bedrooms": ("bedrooms", "recamaras", "habitaciones", "dormitorios"),
    "bathrooms": ("bathrooms", "banos", "bano", "wc"),
    "latitude": ("latitude", "latitud", "lat"),
    "longitude": ("longitude", "longitud", "lon", "lng"),
    "observed_at": ("observed_at", "fecha", "date", "fecha_publicacion", "fecha_captura"),
}


@dataclass(slots=True)
class NormalizationReport:
    dataset_id: str
    asset_path: str
    rows_input: int
    rows_output: int
    mapping: dict[str, str]
    missing_core_fields: list[str]
    invalid_price_rows: int
    invalid_coordinate_rows: int
    duplicate_external_ids: int


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def resolve_mapping(columns: list[str]) -> dict[str, str]:
    normalized = {_slug(column): column for column in columns}
    mapping: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            hit = normalized.get(_slug(alias))
            if hit is not None:
                mapping[canonical] = hit
                break
    return mapping


def _read_tabular_asset(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path, low_memory=False)
    if ext == ".parquet":
        return pd.read_parquet(path)
    if ext == ".xlsx":
        return pd.read_excel(path)
    raise ValueError(f"Asset is not a supported tabular listing file: {ext}")


def normalize_frame(frame: pd.DataFrame, dataset_id: str, asset_path: str) -> tuple[pd.DataFrame, NormalizationReport]:
    mapping = resolve_mapping([str(column) for column in frame.columns])
    core = ["price", "latitude", "longitude"]
    missing_core = [field for field in core if field not in mapping]

    canonical = pd.DataFrame(index=frame.index)
    for target, source in mapping.items():
        canonical[target] = frame[source]

    for numeric in ("price", "area_land_m2", "area_built_m2", "bedrooms", "bathrooms", "latitude", "longitude"):
        if numeric in canonical:
            canonical[numeric] = pd.to_numeric(canonical[numeric], errors="coerce")

    if "observed_at" in canonical:
        canonical["observed_at"] = pd.to_datetime(canonical["observed_at"], errors="coerce").dt.date

    if "external_id" not in canonical:
        canonical["external_id"] = [f"{dataset_id}:{asset_path}:{i}" for i in range(len(canonical))]
    else:
        canonical["external_id"] = canonical["external_id"].astype("string")
        missing_id = canonical["external_id"].isna() | canonical["external_id"].str.strip().eq("")
        canonical.loc[missing_id, "external_id"] = [
            f"{dataset_id}:{asset_path}:{i}" for i in canonical.index[missing_id]
        ]

    invalid_price = int((canonical.get("price", pd.Series(index=canonical.index, dtype=float)) <= 0).fillna(False).sum())
    lat = canonical.get("latitude", pd.Series(index=canonical.index, dtype=float))
    lon = canonical.get("longitude", pd.Series(index=canonical.index, dtype=float))
    coordinate_present = lat.notna() | lon.notna()
    valid_coordinates = lat.between(-90, 90) & lon.between(-180, 180)
    invalid_coordinates = int((coordinate_present & ~valid_coordinates).sum())

    if "price" in canonical:
        canonical.loc[canonical["price"] <= 0, "price"] = np.nan
    if "latitude" in canonical and "longitude" in canonical:
        canonical.loc[~valid_coordinates, ["latitude", "longitude"]] = np.nan

    duplicate_ids = int(canonical["external_id"].duplicated(keep=False).sum())
    canonical = canonical.drop_duplicates(subset=["external_id"], keep="last").copy()

    passthrough_columns = set(mapping.values())
    extra_columns = [column for column in frame.columns if column not in passthrough_columns]
    if extra_columns:
        canonical["attributes"] = frame.loc[canonical.index, extra_columns].apply(
            lambda row: json.dumps(
                {str(key): None if pd.isna(value) else value for key, value in row.items()},
                ensure_ascii=False,
                default=str,
            ),
            axis=1,
        )
    else:
        canonical["attributes"] = "{}"

    report = NormalizationReport(
        dataset_id=dataset_id,
        asset_path=asset_path,
        rows_input=len(frame),
        rows_output=len(canonical),
        mapping=mapping,
        missing_core_fields=missing_core,
        invalid_price_rows=invalid_price,
        invalid_coordinate_rows=invalid_coordinates,
        duplicate_external_ids=duplicate_ids,
    )
    return canonical, report


def persist_properties(dataset_id: str, frame: pd.DataFrame) -> int:
    records = frame.where(pd.notna(frame), None).to_dict(orient="records")
    if not records:
        return 0

    statement = text(
        """
        INSERT INTO properties(
            dataset_id, external_id, address, neighborhood, property_type, listing_type,
            price, area_land_m2, area_built_m2, bedrooms, bathrooms,
            latitude, longitude, geom, observed_at, attributes
        ) VALUES (
            CAST(:dataset_id AS uuid), :external_id, :address, :neighborhood, :property_type, :listing_type,
            :price, :area_land_m2, :area_built_m2, :bedrooms, :bathrooms,
            :latitude, :longitude,
            CASE WHEN :latitude IS NOT NULL AND :longitude IS NOT NULL
                 THEN ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)
                 ELSE NULL END,
            :observed_at, CAST(:attributes AS jsonb)
        )
        ON CONFLICT (dataset_id, external_id) DO UPDATE SET
            address = EXCLUDED.address,
            neighborhood = EXCLUDED.neighborhood,
            property_type = EXCLUDED.property_type,
            listing_type = EXCLUDED.listing_type,
            price = EXCLUDED.price,
            area_land_m2 = EXCLUDED.area_land_m2,
            area_built_m2 = EXCLUDED.area_built_m2,
            bedrooms = EXCLUDED.bedrooms,
            bathrooms = EXCLUDED.bathrooms,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            geom = EXCLUDED.geom,
            observed_at = EXCLUDED.observed_at,
            attributes = EXCLUDED.attributes
        """
    )

    keys = [
        "external_id", "address", "neighborhood", "property_type", "listing_type", "price",
        "area_land_m2", "area_built_m2", "bedrooms", "bathrooms", "latitude", "longitude",
        "observed_at", "attributes",
    ]
    payload = []
    for record in records:
        item = {key: record.get(key) for key in keys}
        item["dataset_id"] = dataset_id
        item["attributes"] = item.get("attributes") or "{}"
        payload.append(item)

    with engine.begin() as conn:
        conn.execute(statement, payload)
        conn.execute(
            text(
                """
                UPDATE datasets
                SET status = 'normalized', updated_at = now()
                WHERE id = CAST(:dataset_id AS uuid)
                """
            ),
            {"dataset_id": dataset_id},
        )
    return len(payload)


def normalize_asset(dataset_id: str, asset_path: str) -> NormalizationReport:
    root = (settings.data_dir / dataset_id / "raw").resolve()
    path = (root / asset_path).resolve()
    if root not in path.parents:
        raise ValueError("Asset path escapes dataset root")
    if not path.exists():
        raise ValueError("Asset not found for dataset")

    frame = _read_tabular_asset(path)
    normalized, report = normalize_frame(frame, dataset_id, asset_path)
    persist_properties(dataset_id, normalized)

    report_path = settings.data_dir / dataset_id / "normalization-report.json"
    report_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return report
