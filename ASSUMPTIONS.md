# ASSUMPTIONS.md

Documento vivo de supuestos. Se ira ampliando conforme avance la solucion.

## A1 - `reference_date` como corte predictivo, no filtro global de limpieza

- **Que dice el spec ambiguamente**: `reference_date` aparece como snapshot del analisis, pero el CSV tambien puede contener transacciones con fecha posterior.
- **Que supuse**: `load_clean` no debe eliminar automaticamente filas posteriores a `reference_date`; solo debe parsearlas y dejarlas disponibles.
- **Como lo verificaria con stakeholder**: preguntaria si el dataset combina historico completo y snapshot predictivo, y que usos esperan para filas posteriores al corte.
- **Impacto si mi supuesto es falso**: algunos analisis descriptivos podrian incluir datos que el evaluador esperaba excluir globalmente. Para modelado y senales de churn aplicare el corte temporal de forma explicita.

## A2 - Outliers de `amount`

- **Que dice el spec ambiguamente**: el enunciado pide limpiar, pero no define reglas de winsorizacion, caps o eliminacion de importes extremos.
- **Que supuse**: `load_clean` no debe eliminar outliers automaticamente; debe convertir importes a numerico y permitir que quality checks o analisis posteriores decidan.
- **Como lo verificaria con stakeholder**: pediria reglas de negocio sobre importes imposibles, chargebacks, reversals y limites por segmento.
- **Impacto si mi supuesto es falso**: KPIs agregados pueden quedar sensibles a importes extremos. Es preferible documentarlo y tratarlo con reglas acordadas antes que inventar umbrales.

## A3 - Variables sospechosas conservadas durante la carga

- **Que dice el spec ambiguamente**: columnas como `cancellation_reason` y `last_complaint_date` son utiles para EDA pero pueden crear leakage en modelado.
- **Que supuse**: `load_clean` debe conservarlas; la exclusion por leakage debe ocurrir al construir features predictivas.
- **Como lo verificaria con stakeholder**: confirmaria que informacion esta disponible en el momento real de prediccion y que informacion es posterior al evento.
- **Impacto si mi supuesto es falso**: si se usan sin filtro temporal en Parte 3, el modelo podria aprender informacion futura. Por eso no se usaran directamente como features predictivas.

## A4 - TPV como volumen aprobado

- **Que dice el spec ambiguamente**: el enunciado pide `tpv`, pero no explicita si incluye intentos fallidos o reversados.
- **Que supuse**: TPV significa volumen de pago procesado con exito, por lo que solo uso transacciones con `status = approved`.
- **Como lo verificaria con stakeholder**: preguntaria si Getnet reporta TPV bruto, neto o aprobado en sus dashboards oficiales.
- **Impacto si mi supuesto es falso**: los KPIs mensuales podrian diferir de reportes financieros que incluyan reversos u otros ajustes contables.

## A5 - Porcentaje e-commerce basado en volumen

- **Que dice el spec ambiguamente**: `pct_ecom` puede interpretarse como porcentaje de transacciones o porcentaje de volumen.
- **Que supuse**: `pct_ecom` es la proporcion del TPV aprobado que viene del canal `ecom`, no la proporcion de conteos.
- **Como lo verificaria con stakeholder**: confirmaria si el indicador se usa para mix de volumen, mix operativo o ambos.
- **Impacto si mi supuesto es falso**: merchants con pocas transacciones e-commerce de alto importe tendrian una lectura distinta si se mide por conteo.

## A6 - Mes de negocio segun `transaction_date`

- **Que dice el spec ambiguamente**: existen `transaction_date` y `dat_process`, y ambas podrian usarse para agrupar por mes.
- **Que supuse**: el mes del KPI se deriva de `transaction_date`; `dat_process` es una fecha operativa de procesamiento.
- **Como lo verificaria con stakeholder**: validaria con el equipo de negocio que los KPIs mensuales se reportan por fecha de transaccion y no por fecha de ingesta/procesamiento.
- **Impacto si mi supuesto es falso**: algunos pagos cerca de cierre de mes podrian asignarse a un mes distinto en dashboards operativos.

## A7 - `quality_report` como auditoria, no limpieza adicional

- **Que dice el spec ambiguamente**: pide un reporte de calidad, pero no define si los problemas deben corregirse automaticamente.
- **Que supuse**: `quality_report` debe detectar y comunicar problemas, no modificar el DataFrame.
- **Como lo verificaria con stakeholder**: preguntaria que problemas deben bloquear el pipeline y cuales deben quedar como warning.
- **Impacto si mi supuesto es falso**: algunos problemas se reportaran pero no se corregiran automaticamente. Esto es intencional para evitar sobrelimpieza sin reglas de negocio.

## A8 - Outliers como warning, no error automático

- **Qué dice el spec ambiguamente**: el enunciado no define qué importe debe considerarse imposible ni qué tratamiento aplicar a valores extremos.
- **Qué supuse**: los importes extremos deben reportarse como casos a revisar, pero no eliminarse automáticamente.
- **Cómo lo verificaría con stakeholder**: validaría límites esperados por país, MCC, segmento y tipo de merchant.
- **Impacto si mi supuesto es falso**: si algunos importes extremos son errores reales, podrían afectar TPV y modelos. Aun así, prefiero no eliminarlos sin regla de negocio explícita.

## A9 - `cancellation_reason` no es señal transaccional

- **Qué dice el spec ambiguamente**: no queda claro si `cancellation_reason` describe una transacción concreta, un merchant o un evento posterior de churn.
- **Qué supuse**: dado que aparece también en transacciones aprobadas y está fuertemente asociada a `fla_churn90`, la trato como información sensible a leakage y no como señal operativa de una transacción.
- **Cómo lo verificaría con stakeholder**: confirmaría cuándo se registra `cancellation_reason` y si estaba disponible antes del snapshot de análisis.
- **Impacto si mi supuesto es falso**: si la columna sí estuviera disponible antes del snapshot, podríamos estar descartando una señal útil. Sin esa confirmación, la opción segura es excluirla de features predictivas.

## A10 - Señal débil de pre-churn

- **Qué dice el spec ambiguamente**: no define qué significa exactamente "señal débil" ni qué ventana temporal usar.
- **Qué supuse**: una señal débil de pre-churn es deterioro reciente de uso o calidad operativa observable antes de `reference_date`: menos TPV, menos transacciones, menor aprobación, más denegadas/reversadas, inactividad o reclamo reciente.
- **Cómo lo verificaría con stakeholder**: contrastaría la heurística con equipos de retención y operaciones, revisando si los merchants priorizados son accionables y si las señales coinciden con casos reales de riesgo.
- **Impacto si mi supuesto es falso**: el ranking puede priorizar merchants con patrones estacionales o de bajo volumen que no estén realmente en riesgo. Por eso lo trato como ranking explicable, no como predicción calibrada.

## A11 - Ventanas temporales para la heurística

- **Qué dice el spec ambiguamente**: no especifica qué periodo usar para comparar actividad reciente frente a actividad anterior.
- **Qué supuse**: uso los últimos 3 meses calendario hasta `reference_date` como periodo reciente y los 3 meses anteriores como periodo base.
- **Cómo lo verificaría con stakeholder**: validaría si negocio prefiere ventanas de 30/60/90 días, meses calendario cerrados o comparación contra el mismo periodo del año anterior.
- **Impacto si mi supuesto es falso**: merchants con estacionalidad fuerte podrían quedar mal priorizados. En producción compararía contra ventanas equivalentes históricas o validaría la heurística con outcomes reales.

## A12 - Inactividad relativa al patrón del merchant

- **Qué dice el spec ambiguamente**: no define cuándo un merchant debe considerarse inactivo o en deterioro.
- **Qué supuse**: un número alto de días desde la última transacción solo es una señal fuerte si es alto respecto al patrón habitual del propio merchant. Por eso comparo `days_since_last_tx` con la mediana histórica de días entre transacciones.
- **Cómo lo verificaría con stakeholder**: validaría si distintos segmentos, MCCs o tipos de merchant tienen cadencias esperadas diferentes.
- **Impacto si mi supuesto es falso**: merchants con transacciones naturalmente poco frecuentes podrían recibir una puntuación incorrecta. La comparación relativa reduce este riesgo, pero no sustituye una validación de negocio.

## A13 - Historial insuficiente antes del snapshot

- **Qué dice el spec ambiguamente**: no especifica cómo tratar merchants que solo tienen transacciones posteriores a `reference_date`.
- **Qué supuse**: si un merchant no tiene transacciones seguras antes del snapshot, no lo trato como inactivo. Lo marco como falta de historial observable y no le asigno riesgo por inactividad.
- **Cómo lo verificaría con stakeholder**: preguntaría si esos merchants son altas recientes, errores de extracción o casos esperados por el diseño del dataset.
- **Impacto si mi supuesto es falso**: si realmente deberían considerarse inactivos, la heurística podría infraestimar su riesgo. Prefiero esta opción porque evita crear señales de churn a partir de ausencia de evidencia.
