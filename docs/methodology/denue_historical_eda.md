# DENUE histórico: reglas de análisis

## Naturaleza del insumo

El archivo histórico usado por Urban es un derivado agregado del DENUE de INEGI, no una copia raw establecimiento-por-establecimiento. Cada fila representa una combinación de AGEB, cuadrícula de 1 km, sector SCIAN, clase SCIAN, estrato de tamaño, código postal y banderas de contacto; `establishments` es el conteo agregado.

Por lo tanto, el panel sí es apropiado para stock, estructura, concentración, diversidad, expansión territorial y comparación espacial. No debe usarse para identificar la supervivencia o cierre de una unidad económica específica sin recuperar antes los microdatos raw con un identificador estable.

## Fechas canónicas

Se conserva `source_edition` para trazabilidad y se añade `edition_date` para ordenar el panel. Las etiquetas 2010, 2011, 2012, 2013-A y 2013-B se canonizan a 07/2010, 03/2011, 06/2012, 07/2013 y 10/2013. La etiqueta fuente `2015-02` se conserva, pero la fecha analítica se registra como 01/2015 porque corresponde a la edición oficial DENUE 01/2015.

## Rebenchmark y rupturas de cobertura

Las ediciones 2015-02, 2019-11 y 2024-11 se marcan con `rebenchmark=True`. Son cortes donde la cobertura puede cambiar de manera importante por actualizaciones censales. Un cambio entre dos ediciones no se interpreta automáticamente como aperturas o cierres netos.

El EDA genera `growth_pct`, crecimiento anualizado y `large_jump` para cambios absolutos de al menos 5%. Estas banderas son diagnósticas; no son evidencia causal ni una regla de exclusión automática.

## Calidad geográfica

`SIN_AGEB`, `SIN_GRID` y `SIN_CP` se conservan y se reportan como tasas ponderadas por establecimientos. No se eliminan silenciosamente. Las cuadrículas son preferibles para comparaciones longitudinales porque la malla es constante; las AGEB pueden cambiar entre marcos geoestadísticos.

Los IDs de cuadrícula no deben considerarse únicos por municipio. Para relaciones territoriales municipales se recomienda la llave `(municipality_code, grid)`; para una geometría física de la malla puede usarse `grid` como identificador de celda, documentando las intersecciones municipales.

## Código postal

`postal_format_valid` solo verifica cinco dígitos. `postal_prefix_plausible_sinaloa` es una heurística de control de calidad basada en prefijos 80/81/82 y no sustituye un catálogo postal oficial. Los modelos no deben usar códigos postales anómalos como coordenadas o proxies espaciales sin validación adicional.

## Diversidad y concentración

El pipeline calcula HHI sectorial, entropía de Shannon y número efectivo de sectores. Estos indicadores se ponderan con el conteo `establishments`, no con el número de filas agregadas.

## Reproducibilidad

El ZIP esperado tiene SHA-256 `182c22a2a96189e47d4e0d6b5dfd2a34a09307cfa3af57b1503664cdecc1bff3`. El pipeline aborta si el archivo descargado no coincide con el tamaño y hash auditados. Las salidas procesadas se guardan como Parquet por edición para evitar reprocesar JSON en cada ejecución.
