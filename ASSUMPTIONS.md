# ASSUMPTIONS.md — `Fornes Reynes, Josep Gabriel`

---

## A1 - `reference_date` como corte predictivo, no filtro global de limpieza

- **Ambigüedad intencional**: `reference_date` aparece como snapshot del análisis, pero el CSV también puede contener transacciones con fecha posterior.
- **Qué supuse**: `reference_date` es el corte temporal para construir señales predictivas. Por eso `load_clean` no elimina globalmente filas posteriores, pero las funciones de riesgo/modelado sí aplican el corte temporal de forma explícita.
- **Cómo lo verificaría con stakeholder**: preguntaría si el dataset combina histórico completo y snapshot predictivo, y qué usos esperan para filas posteriores al corte.
- **Impacto si mi supuesto es falso**: algunos análisis descriptivos podrían incluir datos que el evaluador esperaba excluir globalmente. Para modelado y señales de churn aplico el corte temporal para reducir leakage.

## A2 - Definición de TPV

- **Ambigüedad intencional**: el enunciado pide `tpv`, pero no explicita si incluye intentos fallidos, transacciones denegadas, reversadas o solo aprobadas.
- **Qué supuse**: TPV significa volumen de pago procesado con éxito, por lo que solo sumo `amount` cuando `status = approved`.
- **Cómo lo verificaría con stakeholder**: preguntaría si Getnet reporta TPV bruto, neto o aprobado en sus dashboards oficiales.
- **Impacto si mi supuesto es falso**: los KPIs mensuales y las queries SQL podrían diferir de reportes financieros que incluyan reversos u otros ajustes contables.

## A3 - `pct_ecom` basado en volumen

- **Ambigüedad intencional**: `pct_ecom` puede interpretarse como porcentaje de transacciones e-commerce o como porcentaje de volumen e-commerce.
- **Qué supuse**: `pct_ecom` es la proporción del TPV aprobado que viene del canal `ecom`, no la proporción de conteos.
- **Cómo lo verificaría con stakeholder**: confirmaría si el indicador se usa para mix de volumen, mix operativo o ambos.
- **Impacto si mi supuesto es falso**: merchants con pocas transacciones e-commerce de alto importe tendrían una lectura distinta si se mide por conteo.

---

## Supuestos adicionales

### A4 - Outliers de `amount`

- **Qué dice el spec ambiguamente**: el enunciado pide limpiar, pero no define reglas de winsorización, caps o eliminación de importes extremos.
- **Qué supuse**: `load_clean` no debe eliminar outliers automáticamente, sinó que solo debe convertir importes a numérico y permitir que quality checks o análisis posteriores decidan.
- **Cómo lo verificaría con stakeholder**: pediría reglas de negocio sobre importes imposibles, chargebacks, reversals y límites por segmento.
- **Impacto si mi supuesto es falso**: KPIs agregados pueden quedar sensibles a importes extremos. Es preferible documentarlo y tratarlo con reglas acordadas antes que inventar umbrales.

### A5 - Variables sospechosas conservadas durante la carga

- **Qué dice el spec ambiguamente**: columnas como `cancellation_reason` y `last_complaint_date` son útiles para EDA pero pueden crear leakage en modelado.
- **Qué supuse**: `load_clean` debe conservarlas, ya que la exclusión por leakage debe ocurrir al construir features predictivas.
- **Cómo lo verificaría con stakeholder**: confirmaría qué información está disponible en el momento real de predicción y qué información es posterior al evento.
- **Impacto si mi supuesto es falso**: si se usan sin filtro temporal en Parte 3, el modelo podría aprender información futura. Por eso no se usarán directamente como features predictivas.

### A6 - Mes de negocio según `transaction_date`

- **Qué dice el spec ambiguamente**: existen `transaction_date` y `dat_process`, y ambas podrían usarse para agrupar por mes.
- **Qué supuse**: el mes del KPI se deriva de `transaction_date` y `dat_process` es una fecha operativa de procesamiento.
- **Cómo lo verificaría con stakeholder**: validaría con el equipo de negocio que los KPIs mensuales se reportan por fecha de transacción y no por fecha de procesamiento.
- **Impacto si mi supuesto es falso**: algunos pagos cerca de cierre de mes podrían asignarse a un mes distinto en dashboards operativos.

### A7 - `quality_report` como auditoría, no limpieza adicional

- **Qué dice el spec ambiguamente**: pide un reporte de calidad, pero no define si los problemas deben corregirse automáticamente.
- **Qué supuse**: `quality_report` debe detectar y comunicar problemas, no modificar el DataFrame.
- **Cómo lo verificaría con stakeholder**: preguntaría qué problemas deben bloquear el pipeline y cuáles deben quedar como warning.
- **Impacto si mi supuesto es falso**: algunos problemas se reportarán pero no se corregirán automáticamente. Esto es intencional para evitar sobrelimpieza sin reglas de negocio.

### A8 - Outliers como warning, no error automático

- **Qué dice el spec ambiguamente**: el enunciado no define qué importe debe considerarse imposible ni qué tratamiento aplicar a valores extremos.
- **Qué supuse**: los importes extremos deben reportarse como casos a revisar, pero no eliminarse automáticamente.
- **Cómo lo verificaría con stakeholder**: validaría límites esperados por país, MCC, segmento y tipo de merchant.
- **Impacto si mi supuesto es falso**: si algunos importes extremos son errores reales, podrían afectar TPV y modelos. Aun así, prefiero no eliminarlos sin regla de negocio explícita.

### A9 - `cancellation_reason` no es señal transaccional

- **Qué dice el spec ambiguamente**: no queda claro si `cancellation_reason` describe una transacción concreta, un merchant o un evento posterior de churn.
- **Qué supuse**: dado que aparece también en transacciones aprobadas y está fuertemente asociada a `fla_churn90`, la trato como información sensible a leakage y no como señal operativa de una transacción.
- **Cómo lo verificaría con stakeholder**: confirmaría cuándo se registra `cancellation_reason` y si estaba disponible antes del snapshot de análisis.
- **Impacto si mi supuesto es falso**: si la columna sí estuviera disponible antes del snapshot, podríamos estar descartando una señal útil. Sin esa confirmación, la opción segura es excluirla de features predictivas.

### A10 - Señal débil de pre-churn

- **Qué dice el spec ambiguamente**: no define qué significa exactamente "señal débil" ni qué ventana temporal usar.
- **Qué supuse**: una señal débil de pre-churn es deterioro reciente de uso o calidad operativa observable antes de `reference_date`: menos TPV, menos transacciones, menor aprobación, más denegadas/reversadas, inactividad o reclamo reciente.
- **Cómo lo verificaría con stakeholder**: contrastaría la heurística con equipos de retención y operaciones, revisando si los merchants priorizados son accionables y si las señales coinciden con casos reales de riesgo.
- **Impacto si mi supuesto es falso**: el ranking puede priorizar merchants con patrones estacionales o de bajo volumen que no estén realmente en riesgo. Por eso lo trato como ranking explicable, no como predicción calibrada.

### A11 - Ventanas temporales para la heurística

- **Qué dice el spec ambiguamente**: no especifica qué período usar para comparar actividad reciente frente a actividad anterior.
- **Qué supuse**: uso los últimos 3 meses calendario hasta `reference_date` como período reciente y los 3 meses anteriores como período base.
- **Cómo lo verificaría con stakeholder**: validaría si negocio prefiere ventanas de 30/60/90 días, meses calendario cerrados o comparación contra el mismo período del año anterior.
- **Impacto si mi supuesto es falso**: merchants con estacionalidad fuerte podrían quedar mal priorizados. En producción compararía contra ventanas equivalentes históricas o validaría la heurística con outcomes reales.

### A12 - Inactividad relativa al patrón del merchant

- **Qué dice el spec ambiguamente**: no define cuándo un merchant debe considerarse inactivo o en deterioro.
- **Qué supuse**: un número alto de días desde la última transacción solo es una señal fuerte si es alto respecto al patrón habitual del propio merchant. Por eso comparo `days_since_last_tx` con la mediana histórica de días entre transacciones.
- **Cómo lo verificaría con stakeholder**: validaría si distintos segmentos, MCCs o tipos de merchant tienen cadencias esperadas diferentes.
- **Impacto si mi supuesto es falso**: merchants con transacciones naturalmente poco frecuentes podrían recibir una puntuación incorrecta. La comparación relativa reduce este riesgo, pero no sustituye una validación de negocio.

### A13 - Historial insuficiente antes del snapshot

- **Qué dice el spec ambiguamente**: no especifica cómo tratar merchants que solo tienen transacciones posteriores a `reference_date`.
- **Qué supuse**: si un merchant no tiene transacciones seguras antes del snapshot, no lo trato como inactivo. Lo marco como falta de historial observable y no le asigno riesgo por inactividad.
- **Cómo lo verificaría con stakeholder**: preguntaría si esos merchants son altas recientes, errores de extracción o casos esperados por el diseño del dataset.
- **Impacto si mi supuesto es falso**: si realmente deberían considerarse inactivos, la heurística podría infraestimar su riesgo. Prefiero esta opción porque evita crear señales de churn a partir de ausencia de evidencia.

### A14 - Supuestos de Parte 2 SQL

- **Qué dice el spec ambiguamente**: el enunciado proporciona el esquema lógico de las tablas, pero no detalla constraints, duplicados reales, tipos exactos de fecha ni codificación de país.
- **Qué supuse**: asumí que `merchants` tiene una fila por merchant, `transactions` una fila por transacción y `churn_labels` una fila por merchant y `reference_date`. También asumí que `country = 'BR'` identifica merchants brasileños.
- **Cómo lo verificaría con stakeholder**: revisaría constraints, conteos de duplicados por clave, tipos reales de `transaction_date` y `dat_process`, y valores posibles de `country`.
- **Impacto si mi supuesto es falso**: joins o agregaciones podrían duplicar métricas como TPV o churn rate, y los filtros de país o fechas podrían incluir o excluir filas no esperadas.

### A15 - Períodos temporales en SQL

- **Qué dice el spec ambiguamente**: se piden períodos como Q3 2025 y comparativas mensuales YoY, pero no se especifica si `transaction_date` es `DATE` o `TIMESTAMP`.
- **Qué supuse**: usé intervalos semiabiertos, por ejemplo `[2025-07-01, 2025-10-01)` para Q3 2025, y truncado mensual de `transaction_date` para la comparación 2025 vs 2024.
- **Cómo lo verificaría con stakeholder**: confirmaría la convención temporal usada en reporting oficial y si los timestamps se almacenan con zona horaria.
- **Impacto si mi supuesto es falso**: algunas transacciones cercanas a límites de mes o trimestre podrían asignarse a un período distinto.

### A16 - Modelado a nivel merchant

- **Qué dice el spec ambiguamente**: el CSV está a nivel transacción, pero `fla_churn90` representa churn del merchant.
- **Qué supuse**: el modelo debe entrenarse a nivel merchant, agregando transacciones en features de comportamiento.
- **Cómo lo verificaría con stakeholder**: confirmaría si la unidad de decisión de negocio es merchant, merchant-snapshot o transacción.
- **Impacto si mi supuesto es falso**: entrenar a otro grano podría cambiar las métricas y la interpretación del modelo.

### A17 - Split temporal limitado por un único snapshot

- **Qué dice el spec ambiguamente**: pide un split temporal-aware, pero el dataset parece estar centrado en un snapshot principal.
- **Qué supuse**: evito leakage temporal construyendo features solo hasta `reference_date` y uso split estratificado a nivel merchant para evaluación.
- **Cómo lo verificaría con stakeholder**: pediría snapshots adicionales para hacer una validación out-of-time real.
- **Impacto si mi supuesto es falso**: las métricas pueden ser optimistas frente a una validación temporal real en producción.

### A18 - Interpretabilidad con SHAP

- **Qué dice el spec ambiguamente**: pide interpretabilidad, pero no exige una técnica concreta.
- **Qué supuse**: SHAP es suficiente para obtener top-5 features importantes y justificar el modelo.
- **Cómo lo verificaría con stakeholder**: revisaría si el equipo prefiere explicaciones globales, locales o ambas.
- **Impacto si mi supuesto es falso**: podrían requerirse explicaciones locales por merchant, por ejemplo con LIME o SHAP individual.

### A19 - Uso conservador de features de reclamos en modelado

- **Qué dice el spec ambiguamente**: `last_complaint_date` puede ser útil para predecir churn, pero en el análisis de calidad se detectó que puede contener información posterior al snapshot.
- **Qué supuse**: no uso `last_complaint_date` directamente. Solo uso features derivadas después de filtrar reclamos con fecha menor o igual a `reference_date`.
- **Cómo lo verificaría con stakeholder**: confirmaría cuándo se registra realmente un reclamo y si esa información está disponible en el momento de predicción.
- **Impacto si mi supuesto es falso**: si la fecha de reclamo no es fiable o no está disponible operacionalmente, el modelo podría depender de una señal que no se puede usar en producción. Por eso interpreto esas features con cautela y haría un sanity check sin ellas.

### A20 - Modo mock para evaluación local de Parte 4

- **Qué dice el spec ambiguamente**: permite `MOCK_LLM=1`, pero no define cuánta lógica debe tener el mock.
- **Qué supuse**: el mock debe ser determinístico y suficiente para validar contrato, guardrails, side-effects y tests, pero no pretende medir calidad real de clasificación.
- **Cómo lo verificaría con stakeholder**: confirmaría si el evaluador probará solo mock o también OpenAI con una API key propia.
- **Impacto si mi supuesto es falso**: si esperan evaluar calidad semántica en modo mock, las reglas pueden parecer demasiado simples. Para calidad real usaría el agente Agno con OpenAI y un golden set.

### A21 - Merchant sin contexto en `merchants_context.json`

- **Qué dice el spec ambiguamente**: no especifica qué hacer si un `merchant_id` no aparece en el JSON de contexto.
- **Qué supuse**: la API debe responder igualmente y marcar `merchant_context_used=False`, sin fallar.
- **Cómo lo verificaría con stakeholder**: preguntaría si la ausencia de contexto debe degradar la urgencia, escalarse o tratarse como caso normal.
- **Impacto si mi supuesto es falso**: algunos merchants podrían recibir clasificación con menos información de la esperada.

### A22 - PII redaction basada en regex

- **Qué dice el spec ambiguamente**: pide redactar PII, pero no define todos los tipos de PII ni el nivel de cobertura.
- **Qué supuse**: para esta prueba cubro emails, teléfonos y tarjetas con regex simples antes del LLM.
- **Cómo lo verificaría con stakeholder**: validaría requisitos legales/compliance y formatos locales adicionales como CPF, CNPJ o IBAN.
- **Impacto si mi supuesto es falso**: podrían escaparse formatos de PII no cubiertos. En producción usaría un detector DLP más robusto.

### A23 - Coste real no medido

- **Qué dice el spec ambiguamente**: pide estimar coste mensual para 5.000 emails/día, pero no proporciona longitud media de emails, tokens reales, modelo final validado ni precio congelado.
- **Qué supuse**: en esta entrega documento el método de estimación y un valor aproximado, pero no doy una cifra cerrada como si fuera coste real medido.
- **Cómo lo verificaría con stakeholder**: mediría tokens sobre una muestra representativa de emails reales y confirmaría el modelo/proveedor final.
- **Impacto si mi supuesto es falso**: una estimación sin medición real podría infraestimar o sobreestimar el coste, por eso prefiero dejar explícita la limitación.