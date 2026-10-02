# DENUE EDA en Google Colab

La rama `feat/denue-colab-workspace` está diseñada para ejecutar el flujo DENUE sin volver a subir manualmente el ZIP en cada sesión.

## Flujo

1. Colab clona `Murua-Alvaro/urban`.
2. Instala `requirements-colab.txt` y el paquete `urban-denue`.
3. El loader busca el archivo auditado en GitHub (`data/denue-historico`).
4. Verifica tamaño y SHA-256 antes de usarlo.
5. Reutiliza caché si ya existe una copia válida.
6. Ejecuta por etapas: `load`, `validate`, `clean`, `eda`, `spatial`, `features` o `all`.
7. Los resultados quedan en `DENUE_ROOT`; opcionalmente puede apuntarse a Google Drive para persistir entre sesiones.

## Archivo esperado

`data/denue/raw/Growa_DENUE_Sinaloa_Historico_2010_2026.zip`

SHA-256 esperado:

`182c22a2a96189e47d4e0d6b5dfd2a34a09307cfa3af57b1503664cdecc1bff3`

## Ejecución rápida

```bash
python scripts/denue/colab_entrypoint.py --stage eda --root /content/urban-denue
```

Pipeline completo:

```bash
python scripts/denue/colab_entrypoint.py --stage all --root /content/urban-denue
```

Para calcular Moran I en lugar de omitirlo en ejecuciones rápidas:

```bash
python scripts/denue/colab_entrypoint.py --stage all --root /content/urban-denue --with-moran
```

## Caché persistente con Google Drive

En Colab puede montarse Drive y usar, por ejemplo:

`/content/drive/MyDrive/urban-denue-cache`

como `DENUE_ROOT`. De esa manera el ZIP verificado, los Parquet y otros outputs sobreviven al reinicio del runtime. GitHub sigue siendo la fuente versionada; Drive funciona solamente como caché de ejecución.

## Principio de reproducibilidad

El raw no se edita. La limpieza crea derivados canónicos. El EDA consume Parquet reproducibles y los modelos consumen el feature store. Los rebenchmarks 2015, 2019 y 2024 se conservan explícitamente para evitar interpretarlos como crecimiento orgánico sin control.
