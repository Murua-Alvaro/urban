# DENUE raw archive slot

Subir en esta carpeta, sin renombrarlo:

`Growa_DENUE_Sinaloa_Historico_2010_2026.zip`

Archivo auditado esperado:

- Tamaño: `14,147,652` bytes
- SHA-256: `182c22a2a96189e47d4e0d6b5dfd2a34a09307cfa3af57b1503664cdecc1bff3`
- Tipo: ZIP válido
- Cobertura: 25 cortes DENUE, 2010 a 2026-05
- Naturaleza: panel territorial derivado/agregado; no es el microdato raw establecimiento-por-establecimiento.

El pipeline de `scripts/denue/fetch_archive.py` valida tamaño y SHA-256 antes de procesar. Si no coinciden, la ejecución se detiene.
