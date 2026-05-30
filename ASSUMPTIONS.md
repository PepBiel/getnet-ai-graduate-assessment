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
