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

### D7 - Heurística de `merchants_at_risk`

- **Qué hice**: implementé `merchants_at_risk` como una heurística vectorizada de señales débiles de pre-churn a nivel merchant.
- **Señales usadas**: caída reciente de TPV, caída de número de transacciones, caída de approval rate, tasa reciente de transacciones `denied`/`reversed`, días desde la última transacción, inactividad relativa al ritmo histórico del merchant y reclamo reciente válido antes de `reference_date`.
- **Por qué**: el enunciado pide una "señal débil" de pre-churn, no un modelo supervisado. Estas señales son interpretables y se pueden explicar a negocio como deterioro de uso, fricción operativa o falta de actividad antes del snapshot.
- **Ventanas temporales**: comparé los últimos 3 meses calendario hasta `reference_date` contra los 3 meses anteriores. Esta ventana es simple, interpretable y suficiente para una heurística inicial, aunque debería validarse con negocio si se usara fuera del contexto del take-home.
- **Puntuación**: usé una puntuación ponderada: 35 puntos para caída de TPV, 20 para caída de transacciones, 15 para caída de approval rate, 10 para tasa de estados negativos, 10 para inactividad y 10 para reclamo reciente. El score es relativo e interpretable, no una probabilidad calibrada.
- **Qué descarté**: no usé `fla_churn90`, `cancellation_reason`, transacciones posteriores a `reference_date` ni reclamos posteriores a `reference_date`, porque introducirían leakage o información no disponible en el snapshot.
- **Matiz de historial insuficiente**: si un merchant solo tiene transacciones posteriores a `reference_date`, no interpreto esa ausencia de histórico seguro como inactividad real. Lo trato como falta de historial observable antes del snapshot y no le asigno riesgo por inactividad salvo que existan otras señales válidas.
- **Matiz de inactividad**: no comparo únicamente contra un umbral fijo de días sin transaccionar; también comparo `days_since_last_tx` con la mediana histórica de días entre transacciones del propio merchant. Esto evita penalizar injustamente a merchants que normalmente transaccionan con poca frecuencia.
- **Uso de `fla_churn90`**: no usé `fla_churn90` para construir `risk_score`, seleccionar señales ni ordenar merchants. La heurística se basa únicamente en señales disponibles antes o en `reference_date`.
- **Comparación posterior con el target**: comparé el top 200 contra `fla_churn90` solo como evaluación descriptiva posterior. Esta comparación ayuda a entender si el ranking captura más churners que la tasa base, pero no constituye una validación robusta porque se realiza sobre el mismo dataset de trabajo y no sobre un holdout temporal independiente.
- **Interpretación del resultado**: el resultado descriptivo del top 200 no mejora claramente la tasa base de churn. Por tanto, considero esta heurística interpretable y útil para priorización exploratoria, pero no predictivamente validada.
- **Trade-off**: el score no está calibrado ni validado contra outcomes externos; sirve para priorizar revisión humana o exploración inicial, no para automatizar decisiones comerciales.


## Parte 2 - SQL

### D8 - Lectura del modelo de datos del warehouse

- **Qué hice**: antes de escribir las queries, interpreté el significado, grano y uso esperado de cada tabla (`merchants`, `transactions`, `churn_labels`). El objetivo fue evitar joins incorrectos, duplicaciones accidentales y agregaciones a un nivel equivocado.

- **Grano asumido**:
  - `merchants`: una fila por merchant.
  - `transactions`: una fila por transacción.
  - `churn_labels`: una fila por merchant y `reference_date`.

- **Relaciones**:
  - `merchants` se une con `transactions` por `merchant_id`.
  - `merchants` se une con `churn_labels` por `merchant_id`.
  - `transactions` puede tener muchas filas por merchant, por lo que cualquier métrica transaccional debe agregarse antes de interpretarse a nivel merchant.
  - `churn_labels` puede contener distintos snapshots para un mismo merchant, por lo que siempre filtro por `reference_date` cuando calculo churn.

- **Supuestos sobre campos**:
  - `transaction_date` es la fecha de negocio para trimestres, meses y comparativas temporales.
  - `dat_process` es fecha de procesamiento/partición y puede usarse para optimización, pero no como sustituto de la fecha de negocio.
  - `amount` se asume numérico en warehouse. Si viniera como string con formato local, habría que parsearlo antes de calcular TPV.
  - `status = 'approved'` representa transacción aprobada y es el estado que contribuye a TPV.
  - `country = 'BR'` identifica merchants brasileños.
  - `mcc` es categórico aunque pueda estar codificado como número.
  - `fla_churn90` es una etiqueta a nivel merchant-snapshot, no una feature predictiva.

- **Decisiones derivadas de este análisis**:
  - Las métricas de TPV y approval rate se calculan desde `transactions`.
  - Las métricas de churn se calculan a nivel merchant usando `churn_labels`.
  - Para evitar mezclar snapshots, las consultas de churn filtran explícitamente `reference_date = DATE '2025-09-30'`.
  - En las comparativas temporales uso `transaction_date`, manteniendo `dat_process` solo como posible ayuda de particionado/pruning.

- **Riesgo si el supuesto es falso**: si `merchants` o `churn_labels` tienen duplicados no controlados, los joins pueden duplicar filas y alterar TPV, approval rate o churn rate. Si `transaction_date` y `dat_process` representan lógicas temporales distintas, usar la fecha incorrecta podría asignar transacciones al periodo equivocado.

### D9 - Decisiones específicas de las queries SQL

- **Q1**: interpreté Q3 2025 como el intervalo semiabierto `[2025-07-01, 2025-10-01)`. Preferí esta forma frente a `BETWEEN` para evitar ambigüedades si `transaction_date` contiene timestamp.
- **Q1**: calculé TPV aprobado como suma de `amount` solo cuando `status = 'approved'`, manteniendo la definición usada en Parte 1.
- **Q1**: calculé `approval_rate` como transacciones aprobadas dividido por total de transacciones del periodo.
- **Q2**: calculé churn rate a nivel merchant, no a nivel transacción. Usé una CTE intermedia (`churn_by_segment`) para separar el cálculo de conteos del filtro `n_merchants >= 100`.
- **Q3**: agregué TPV mensual por merchant y después hice un self-join contra el mismo mes del año anterior usando `ADD_MONTHS(month, -12)`.
- **Q3**: si no existe TPV para el mismo mes de 2024, devuelvo `0` con `COALESCE`, interpretándolo como ausencia de volumen observado ese mes.
- **Q4**: expliqué `dat_process` como una columna útil para partition pruning, pero manteniendo `transaction_date` como fecha de negocio.
- **Trade-off**: no añadí lógica extra de deduplicación o normalización avanzada en las queries porque el enunciado presenta un esquema lógico de warehouse. Si los datos reales tuvieran duplicados o valores no normalizados, añadiría CTEs previas de validación/limpieza.