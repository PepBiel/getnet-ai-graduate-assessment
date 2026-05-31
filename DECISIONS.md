# DECISIONS.md

Documento vivo de decisiones tecnicas. Cada seccion se ira ampliando conforme avance la solucion.

## Parte 1 - Pandas

### D1 - Exploracion antes de limpiar

- **Que hice**: cree un notebook de exploracion para visualizar formatos, nulos, duplicados y patrones temporales antes de implementar la limpieza reproducible en `src/parte1_pandas.py`.
- **Por que**: limpiar directamente sin mirar los datos puede ocultar problemas de calidad o introducir supuestos no defendibles. La exploracion separa observacion de datos y transformacion productiva.
- **Que descarte**: modificar el CSV original o limpiar de forma manual desde el notebook. El notebook queda como apoyo de EDA; la logica reutilizable vive en funciones.
- **Que supuse**: el CSV de entrada debe tratarse como read-only y cualquier transformacion debe ser reproducible desde codigo.

### D2 - Tratamiento de tipos en `load_clean`

- **Que hice**: parseo `amount` desde formato con coma decimal, parseo `transaction_date`, `reference_date`, `last_complaint_date` y `dat_process`, normalizo `status` y `channel`, y trato `mcc` como string.
- **Por que**: esos campos no son analizables de forma segura como strings originales. `mcc` es un codigo de categoria, no una magnitud numerica.
- **Que descarte**: usar `astype(float)` para importes, confiar en inferencia automatica de fechas o dejar `mcc` como entero.
- **Que supuse**: los importes siguen convencion local con `.` como miles y `,` como decimal; las fechas observadas pueden venir en ISO o `DD/MM/YYYY`.

### D3 - Trazabilidad y no sobrelimpieza

- **Que hice**: conserve columnas `*_raw` para importes y fechas antes de parsearlas; no elimine `cancellation_reason`, `last_complaint_date`, outliers ni filas posteriores a `reference_date` dentro de `load_clean`.
- **Por que**: `load_clean` debe producir un dataset limpio y auditable para analisis general. Los filtros predictivos deben aplicarse despues, donde el objetivo temporal sea explicito.
- **Que descarte**: filtrar globalmente todo lo posterior a `reference_date`, imputar importes nulos o eliminar variables sospechosas durante la carga.
- **Que supuse**: algunas transacciones posteriores a `reference_date` pueden servir para EDA, validaciones o controles de calidad, aunque no deben usarse para features predictivas.

### D4 - Deduplicacion por negocio

- **Que hice**: deduplique por columnas de negocio excluyendo `transaction_id` y columnas `*_raw`.
- **Por que**: `transaction_id` puede ser unico aunque dos filas representen el mismo evento de negocio. Excluir columnas raw evita que un mismo evento no se detecte como duplicado solo por diferencias de formato ya normalizadas.
- **Que descarte**: deduplicar solo por `transaction_id` o eliminar duplicados antes de parsear tipos.
- **Que supuse**: si todas las columnas de negocio normalizadas coinciden, conservar la primera fila es suficiente para KPIs de esta prueba.

### D5 - Definiciones de KPIs mensuales

- **Que hice**: calcule KPIs mensuales a nivel `merchant_id` x `month`, usando `transaction_date` para derivar el mes calendario.
- **Definiciones**: `tpv` es la suma de `amount` para transacciones con `status = approved`; `approval_rate` es transacciones aprobadas dividido por transacciones totales; `pct_ecom` es TPV aprobado de canal `ecom` dividido por TPV aprobado total; `n_tx` es el numero total de transacciones del merchant-mes.
- **Por que**: TPV representa volumen de pagos procesado con exito, por lo que las transacciones denegadas o reversadas no contribuyen al volumen. En cambio, `n_tx` incluye todos los estados porque mide actividad e intentos, no solo pagos exitosos.
- **Que descarte**: contar `pct_ecom` por numero de transacciones, incluir denegadas/reversadas en TPV, filtrar por `reference_date` dentro de una funcion general de agregacion o eliminar outliers durante el calculo mensual.
- **Trade-off**: los importes faltantes en transacciones aprobadas no se imputan, asi que el TPV puede quedar subestimado en merchant-meses afectados. Prefiero dejar visible el problema para `quality_report` antes que inventar volumen.

### D6 - Reporte de calidad de datos

- **Qué hice**: implementé `quality_report` como un reporte estructurado con problemas detectados, filas afectadas, impacto y propuesta de corrección.
- **Por qué**: el objetivo no es solo limpiar datos, sino dejar evidencia de los riesgos encontrados para que otra persona pueda mantener o auditar el pipeline.
- **Qué incluí**: importes missing, importes missing en transacciones aprobadas, fallos de parseo, formatos mixtos, importes extremos para revisión, duplicados de negocio, inconsistencias temporales respecto a `reference_date`, riesgo de leakage en `cancellation_reason`, presencia de `cancellation_reason` en transacciones aprobadas, target desbalanceado y valores categóricos inesperados.
- **Qué descarté**: no traté todos los problemas como errores a eliminar. Algunos, como outliers o transacciones posteriores a `reference_date`, se reportan para que el tratamiento dependa del uso posterior.
- **Trade-off**: el reporte es conservador y puede marcar situaciones que son válidas para análisis descriptivo, pero no seguras para modelado predictivo. Prefiero explicitar estos riesgos antes que ocultarlos durante la limpieza.
- **Summary adicional**: añadí métricas de contexto como número de merchants, tasa positiva del target a nivel fila y merchant, consistencia del target por merchant y percentiles/resumen de importes para facilitar la revisión posterior.