# Modelado de dinámica DENUE por cuadrícula

Los modelos de `feat/denue-analysis` son exploratorios y predictivos. El objetivo es anticipar el stock registrado de establecimientos de la siguiente edición por cuadrícula municipal; no estimar un efecto causal de diversidad, digitalización u otra variable.

## Muestra primaria

La muestra primaria excluye observaciones cuyo objetivo corresponde a los rebenchmark 01/2015, 11/2019 y 11/2024. Se conserva una sensibilidad que incluye todos los cortes. Esto evita que las actualizaciones censales más grandes dominen los parámetros de dinámica ordinaria.

## Especificaciones

1. OLS sobre `log(1 + stock siguiente)` con errores HC3, efectos fijos categóricos de municipio y edición y controles de stock actual, diversidad, HHI, número de sectores/clases y presencia de teléfono, email y web.
2. Poisson QMLE sobre el conteo de la siguiente edición con la misma estructura y covarianza robusta HC3.
3. Random Forest para predicción fuera de muestra. La validación espacial usa `GroupKFold` con `municipality|grid` como grupo, de modo que una misma cuadrícula no aparece simultáneamente en entrenamiento y prueba.
4. Holdouts temporales rolling-origin para las últimas ediciones objetivo disponibles.

## Baseline

Cada evaluación de ML se compara contra una regla de persistencia: predecir que el stock de la siguiente edición será igual al stock actual. Por ello, un modelo complejo solo se considera útil si mejora MAE/RMSE fuera de muestra respecto de esa baseline.

## Interpretación

Los coeficientes describen asociaciones condicionales. No deben presentarse como causalidad porque la localización de actividades, el stock empresarial y la diversidad son endógenos y responden conjuntamente a accesibilidad, renta, población, shocks, regulación y otras variables no incluidas.

## Extensiones previstas

La capa siguiente debe incorporar geometría real, vecinos espaciales, rezagos espaciales, población/demografía, accesibilidad, empleo y validación leave-one-city/municipality-out. Para inferencia espacial se deben probar matrices Queen/Rook/KNN/radios y reportar sensibilidad.
