# DENUE histórico

Esta carpeta está reservada para la serie histórica de DENUE que alimentará Urban.

## Estructura propuesta

```text
data/denue/
  raw/
    2011/
    2012/
    ...
    2025/
  manifests/
    denue_files.csv
  processed/
```

- `raw/`: archivos originales, sin modificar, separados por año.
- `manifests/`: inventario de archivos, hashes SHA-256, año, cobertura y estado de procesamiento.
- `processed/`: productos derivados reproducibles; no sustituye al dato original.

## Reglas

1. Nunca sobrescribir silenciosamente un archivo original.
2. Cada archivo debe registrar año, nombre original, SHA-256 y tamaño.
3. Los datos procesados deben poder reconstruirse desde `raw/`.
4. La fuente oficial debe conservarse separada de cualquier seed o dato sintético.
5. Si un ZIP supera los límites de GitHub normal, se almacenará mediante un mecanismo de archivos grandes y el repositorio conservará su manifiesto y referencia.

La meta es integrar después estos archivos al esquema PostGIS de Urban para análisis por establecimiento, SCIAN, AGEB, colonia, manzana y cuadrícula, conservando la dimensión temporal.
