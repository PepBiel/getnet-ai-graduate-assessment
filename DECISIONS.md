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

- **Qué hice**: conservé columnas `*_raw` para los campos que iban a ser transformados (`amount`, `transaction_date`, `reference_date`, `last_complaint_date`, `dat_process`). Después parseé las versiones limpias, pero mantuve las originales para trazabilidad, auditoría y posibles análisis posteriores.
- **Por qué**: `load_clean` debe producir un dataset limpio y auditable para análisis general. Mantener las columnas originales permite revisar errores de parseo, validar supuestos de formato y reutilizar la información raw si en partes posteriores se necesita otro tratamiento.
- **Qué descarté**: sobrescribir sin trazabilidad los valores originales, filtrar globalmente todo lo posterior a `reference_date`, imputar importes nulos o eliminar variables sospechosas durante la carga.
- **Qué supuse**: algunas transacciones posteriores a `reference_date` pueden servir para EDA, validaciones o controles de calidad, aunque no deben usarse para features predictivas.
- **Trade-off**: conservar columnas `*_raw` aumenta ligeramente el tamaño del DataFrame, pero mejora la auditabilidad y evita perder información útil para debugging, `quality_report` o ejercicios posteriores.

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


## Parte 3 - Modelado ML

### D10 - Grano del dataset de modelado

- **Qué hice**: construí un dataset de modelado a nivel merchant, agregando transacciones en features de comportamiento antes de entrenar.
- **Por qué**: `fla_churn90` es una etiqueta de churn a nivel merchant/snapshot, no a nivel transacción individual. Entrenar a nivel transacción haría que merchants con más transacciones pesaran más y podría distorsionar la evaluación.
- **Qué descarté**: no entrené directamente sobre filas transaccionales.
- **Qué supuse**: cada merchant tiene una única etiqueta válida para el snapshot de análisis.

### D11 - Features descartadas por leakage o baja generalización

- **Qué hice**: descarté `cancellation_reason`, `last_complaint_date` directa, `merchant_id`, `transaction_id`, `fla_churn90`, `reference_date`, `dat_process` y columnas `*_raw`.
- **Por qué**: `cancellation_reason` parece información post-evento; `last_complaint_date` puede contener información posterior al snapshot; los IDs pueden inducir memorización; `dat_process` es operativo; las columnas raw son de trazabilidad.
- **Qué usé en su lugar**: agregados seguros hasta `reference_date`, como TPV reciente, caída de TPV, approval rate, fricción operativa, canal, cadencia de transacción y reclamos seguros.
- **Riesgo si me equivoco**: podría estar descartando una señal útil si estuviera disponible antes del snapshot, pero prefiero evitar leakage no justificado.

### D12 - Análisis de correlación entre features

- **Qué hice**: después de construir features seguras a nivel merchant, revisé la correlación Spearman entre variables numéricas para detectar redundancias fuertes.
- **Por qué**: algunas métricas de volumen, actividad y ratios pueden estar relacionadas. Revisar correlaciones ayuda a evitar features duplicadas y a interpretar mejor los modelos, especialmente el baseline lineal.
- **Qué no hice**: no usé correlación para decidir si una variable con posible leakage debía conservarse. Las columnas sospechosas se descartan por disponibilidad temporal y lógica de negocio, no por su correlación.
- **Decisión**: no eliminé automáticamente todas las variables correlacionadas. Mantuve features interpretables cuando representaban señales de negocio distintas.
- **Trade-off**: mantener features correlacionadas puede repartir importancia entre variables similares, especialmente en modelos de árboles.

### D13 - Split y evaluación del modelo

- **Qué hice**: construí features usando solo información con fecha menor o igual a `reference_date` y después hice un split estratificado a nivel merchant.
- **Por qué**: el target está desbalanceado y el dataset parece tener un snapshot principal, por lo que mantuve la proporción de churn en train/test sin mezclar información futura en las features.
- **Limitación**: si solo hay un snapshot, este split no es una validación temporal out-of-time real. Para producción, validaría en snapshots posteriores.
- **Métricas**: usé ROC-AUC, PR-AUC / Average Precision, Brier score y precision/recall@k, evitando accuracy como métrica principal.

### D14 - Modelos e interpretabilidad

- **Qué hice**: entrené una Logistic Regression como baseline interpretable y un XGBoost como modelo no lineal más potente.
- **Por qué**: la regresión logística sirve como referencia simple y XGBoost puede capturar interacciones no lineales en datos tabulares.
- **Interpretabilidad**: usé SHAP para explicar el modelo final y obtener el top-5 de features por importancia media absoluta.
- **Qué descarté**: no añadí LIME para evitar introducir una dependencia adicional. SHAP ya está disponible en el entorno y cubre el requisito de interpretabilidad global.
- **Matiz**: la importancia de features indica asociación con la predicción, no causalidad.

### D15 - Lectura de resultados y limitaciones del modelo

- **Qué observé**: los modelos muestran señal moderada, no una separación fuerte. El ROC-AUC está alrededor de 0.60–0.62 y la Average Precision mejora ligeramente la tasa base de churn.
- **Por qué importa**: esto sugiere que las features construidas aportan algo de señal, pero el modelo no debe interpretarse como una solución predictiva robusta ni lista para producción.
- **Calibración**: el Brier score indica que las probabilidades no están bien calibradas. Esto puede deberse al uso de `class_weight` y `scale_pos_weight`, que ayudan al ranking pero pueden distorsionar probabilidades.
- **Interpretabilidad**: varias features importantes están relacionadas con reclamos seguros. Las mantengo porque aplican filtro temporal, pero las interpreto con cautela por los problemas de calidad detectados en `last_complaint_date`.
- **Trade-off**: prioricé un pipeline reproducible y anti-leakage frente a optimizar métricas. No ajusté hiperparámetros agresivamente para evitar sobreoptimizar este único dataset.
