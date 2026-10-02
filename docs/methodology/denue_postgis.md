# DENUE histórico en PostGIS

## Objetivo

Persistir el panel territorial derivado del DENUE de Sinaloa con trazabilidad completa hacia el ZIP auditado, sin presentar las filas agregadas como microdatos de establecimientos individuales.

## Modelo

- `datasets`: registra una sola vez el archivo fuente con SHA-256 `182c22a2a96189e47d4e0d6b5dfd2a34a09307cfa3af57b1503664cdecc1bff3`.
- `denue_editions`: 25 cortes con fecha analítica y bandera `is_rebenchmark`.
- `denue_observations`: combinaciones agregadas municipio–AGEB–grid–sector–tamaño–SCIAN6–CP–flags, ponderadas por `establishments`.
- `denue_grid_geometries`: geometrías de la malla por `(municipality_code, grid_id)` porque una celda física puede intersectar más de un municipio.

## Importación

El cargador usa PostgreSQL `COPY` para no ejecutar millones de `INSERT` individuales. Cada edición se reemplaza dentro de una transacción independiente. Si falla la validación de cualquier municipio, esa edición se revierte completa.

Por defecto una edición que ya tiene observaciones se omite. `--replace` fuerza su recarga desde el insumo auditado.

Ejemplo, una vez que estén disponibles la extracción DENUE y `DATABASE_URL`:

```bash
pip install -r requirements-denue-db.txt
python scripts/denue/load_postgis.py --apply-migration
```

Para recargar todas las ediciones:

```bash
python scripts/denue/load_postgis.py --replace
```

## Verificación posterior

La carga se considera correcta solamente si pasan los smoke totals incorporados:

- Sinaloa 2010: 94,961
- Sinaloa 2015-01 (etiqueta fuente `2015-02`): 107,458
- Sinaloa 2024-11: 135,239
- Sinaloa 2026-05: 138,882
- Mazatlán 2026-05: 27,487
- 25 ediciones asociadas al mismo `dataset_id`

## Consultas

`packages/db/queries/denue_analytics.sql` incluye series municipales, stock/diversidad por grid, LQ, presencia digital, calidad y un panel balanceado de transiciones. El balanceo de grid se limita a ediciones en las que el municipio está efectivamente presente para evitar ceros históricos artificiales en municipios que aparecen posteriormente como unidades separadas.
