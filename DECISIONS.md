# DECISIONS.md

---

## Parte 1 · Pandas

### D1 · Tratamiento de tipos en `load_clean`

- **Qué hice**: parseé `amount` desde formato local con punto de miles y coma decimal. Además, parseé `transaction_date`, `reference_date`, `last_complaint_date` y `dat_process`. Finalmente, normalicé `status` y `channel`, y traté `mcc` como string/categoría.
- **Por qué**: esos campos no eran analizables de forma segura como strings originales. En particular, `amount` no podía convertirse con `astype(float)` sin tratar separadores locales, y `mcc` representa un código de categoría, no una magnitud numérica continua.
- **Qué descarté**: confiar en inferencia automática de fechas, convertir importes directamente con `astype(float)`, sobrescribir los valores originales sin trazabilidad y tratar `mcc` como número continuo.
- **Qué supuse**: los importes siguen la convención observada en el CSV (`.` como miles y `,` como decimal), y las fechas pueden aparecer en formato ISO o `DD/MM/YYYY`.

### D2 · Estrategia de trazabilidad y deduplicación

- **Qué hice**: conservé columnas `*_raw` para los campos transformados y dedupliqué por columnas de negocio normalizadas, excluyendo `transaction_id` y columnas raw.
- **Por qué**: mantener valores raw permite auditar errores de parseo y validar supuestos de formato. Deduplicar solo por `transaction_id` no detectaría reenvíos de POS donde el identificador cambia, pero el evento de negocio es el mismo.
- **Qué descarté**: modificar el CSV original, eliminar columnas raw después de limpiar, deduplicar solo por `transaction_id` y eliminar duplicados antes de normalizar tipos.
- **Qué supuse**: si todas las columnas de negocio normalizadas coinciden, conservar la primera fila es suficiente para los KPIs y análisis de esta prueba.

### D3 · KPIs mensuales y definiciones de negocio

- **Qué hice**: calculé KPIs mensuales a nivel `merchant_id` × `month`, usando `transaction_date` para derivar el mes calendario. Definí `tpv` como suma de `amount` en transacciones `approved`, `approval_rate` como aprobadas / totales, `pct_ecom` como TPV aprobado de canal `ecom` / TPV aprobado total y `n_tx` como número total de transacciones.
- **Por qué**: TPV representa volumen de pagos procesado con éxito, por lo que las transacciones denegadas o reversadas no deberían sumar volumen. En cambio, `n_tx` mide actividad o intentos, así que incluye todos los estados.
- **Qué descarté**: incluir transacciones denegadas/reversadas en TPV, calcular `pct_ecom` por conteo de transacciones, filtrar globalmente por `reference_date` dentro de una función general de KPIs y eliminar outliers durante la agregación mensual.
- **Qué supuse**: `transaction_date` es la fecha de negocio para reporting mensual y `pct_ecom` debe leerse como mix de volumen, no como mix de operaciones.

### D4 · Reporte de calidad de datos

- **Qué hice**: implementé `quality_report` como reporte estructurado con problemas detectados, filas afectadas, impacto y propuesta de corrección. Incluí missing values, fallos de parseo, formatos mixtos, outliers, duplicados de negocio, inconsistencias temporales, leakage potencial y valores categóricos inesperados.
- **Por qué**: el objetivo no era solo limpiar, sino dejar evidencia de riesgos para que otra persona pueda mantener o auditar el pipeline. Algunos problemas son warnings para modelado, no errores que deban eliminarse automáticamente.
- **Qué descarté**: corregir automáticamente todos los problemas, imputar importes nulos, eliminar outliers sin reglas de negocio y borrar columnas sospechosas durante la carga.
- **Qué supuse**: `quality_report` debe auditar y comunicar riesgos, no modificar el DataFrame. La decisión de corregir o eliminar depende del uso posterior.

### D5 · Heurística de `merchants_at_risk`

- **Qué hice**: implementé `merchants_at_risk` como una heurística vectorizada de señales débiles de pre-churn a nivel merchant. Usé caída reciente de TPV, caída de transacciones, caída de approval rate, tasa de estados negativos, días desde última transacción, inactividad relativa al ritmo histórico y reclamo reciente válido antes de `reference_date`.
- **Por qué**: el enunciado pide una señal débil, no un modelo supervisado. Elegí señales interpretables que pueden explicarse a negocio como deterioro de uso, fricción operativa o menor actividad antes del snapshot.
- **Qué descarté**: usar `fla_churn90`, `cancellation_reason`, transacciones posteriores a `reference_date`, reclamos posteriores a `reference_date` o una probabilidad calibrada sin validación. Esas variables o ventanas introducirían leakage o harían que la heurística dejara de ser una señal débil previa al churn.
- **Qué supuse**: los últimos 3 meses calendario hasta `reference_date` son una ventana razonable para comparar contra los 3 meses anteriores. También supuse que la inactividad debe interpretarse de forma relativa al patrón histórico del merchant, no como una regla absoluta igual para todos.
- **Limitación observada**: evalué descriptivamente el ranking usando `fla_churn90` solo como variable de comprobación posterior, no para construir la heurística. El objetivo era que el top 200 concentrara más merchants con `fla_churn90 = 1` que la población general. Sin embargo, la `Precision@200` fue aproximadamente 8,5%, frente a una tasa global de churn de aproximadamente 8,7%, por lo que el ranking no mostró lift positivo frente a la tasa base. Por tanto, mantengo la heurística como ranking explicable para exploración, no como predictor validado.

---

## Parte 2 · SQL

### D6 · Lectura del modelo de datos del warehouse

- **Qué hice**: antes de escribir SQL, interpreté el grano de `merchants`, `transactions` y `churn_labels` y definí las relaciones por `merchant_id`.
- **Por qué**: evita joins que dupliquen filas y métricas calculadas a un nivel equivocado. `transactions` puede tener muchas filas por merchant, mientras que `churn_labels` debe filtrarse por snapshot.
- **Qué descarté**: unir tablas y agregar sin revisar grano, usar `dat_process` como fecha de negocio y tratar `fla_churn90` como feature.
- **Qué supuse**: `merchants` tiene una fila por merchant, `transactions` una fila por transacción y `churn_labels` una fila por merchant y `reference_date`.

### D7 · Decisiones específicas de las queries SQL

- **Qué hice**: escribí las queries usando `transaction_date` como fecha de negocio, TPV aprobado como definición de volumen y `reference_date = DATE '2025-09-30'` para churn rate. Para Q3 2025 usé el intervalo semiabierto `[2025-07-01, 2025-10-01)`.
- **Por qué**: los intervalos semiabiertos evitan errores si `transaction_date` contiene timestamps. Mantener la misma definición de TPV que en Parte 1 evita inconsistencias entre Pandas y SQL.
- **Qué descarté**: usar `BETWEEN` para Q3, usar `dat_process` como fecha principal de negocio, deduplicar agresivamente sin evidencia de duplicados en el esquema lógico y mezclar snapshots de churn.
- **Qué supuse**: `country = 'BR'` identifica merchants brasileños y `amount` ya es numérico en warehouse.

---

## Parte 3 · Modelado ML

### D8 · Features descartadas (incluye trampas detectadas)

- **Qué hice**: construí el dataset de modelado a nivel merchant y descarté `cancellation_reason`, `last_complaint_date` directa, `merchant_id`, `transaction_id`, `fla_churn90`, `reference_date`, `dat_process` y columnas `*_raw` como features.
- **Por qué**: `cancellation_reason` parece información post-evento, `last_complaint_date` puede contener información posterior al snapshot, los IDs pueden inducir memorización, `dat_process` es operativo y las columnas raw son trazabilidad, no señal predictiva.
- **Qué descarté**: entrenar directamente sobre filas transaccionales, usar identificadores, usar columnas sospechosas por su alta correlación con el target o introducir información posterior al snapshot.
- **Qué supuse**: `fla_churn90` es una etiqueta a nivel merchant/snapshot, por lo que el modelo debe entrenarse a nivel merchant con agregados temporales seguros.

### D9 · Split temporal-aware y prevención de leakage

- **Qué hice**: construí features usando solo información con fecha menor o igual a `reference_date` y después hice un split estratificado a nivel merchant.
- **Por qué**: el dataset parece tener un snapshot principal, por lo que no puedo hacer una validación out-of-time real. El corte temporal en features reduce leakage, y el split estratificado mantiene la proporción de churn.
- **Qué descarté**: llamar a esto una validación temporal completa, usar un random split a nivel transacción o mezclar información futura en features.
- **Qué supuse**: cada merchant tiene una etiqueta válida para el snapshot y, con los datos disponibles, la evaluación más honesta es un split estratificado con limitación explícita.

### D10 · Métricas y umbralización

- **Qué hice**: evalué Logistic Regression y XGBoost con ROC-AUC, Average Precision / PR-AUC, Brier score y precision/recall@k. También comparé contra una baseline de tasa positiva y revisé calibración.
- **Por qué**: el target está desbalanceado, por lo que accuracy puede ser engañosa. En churn, priorizar un top-k de merchants es más accionable que fijar solo un umbral genérico.
- **Qué descarté**: usar accuracy como métrica principal, optimizar hiperparámetros agresivamente en un único snapshot y presentar probabilidades como calibradas sin validación.
- **Qué supuse**: el uso más razonable del modelo en esta iteración es ranking de riesgo, no decisión automática ni probabilidad calibrada de churn.

### D11 · Interpretabilidad y lectura de resultados

- **Qué hice**: usé SHAP para interpretar el modelo final global y localmente. Añadí top-5 features, true positive, false positive y sanity check sin features de reclamos.
- **Por qué**: el enunciado pide interpretabilidad y era importante comprobar si el modelo dependía demasiado de variables sensibles como reclamos.
- **Qué descarté**: añadir LIME como dependencia extra y sobreinterpretar SHAP como causalidad.
- **Qué supuse**: SHAP es suficiente para explicar contribuciones globales y locales en esta entrega, siempre indicando que son asociaciones del modelo y no causalidad.
- **Limitación observada**: los modelos muestran señal moderada, no una separación fuerte. La Average Precision mejora ligeramente la tasa base, pero no considero el modelo listo para producción.

---

## Parte 4 · FastAPI + Agno

### D12 · Por qué Agno (vs. LangChain / LlamaIndex / código casero)

- **Qué hice**: implementé una API FastAPI con un wrapper de agente que puede usar Agno/OpenAI o un `_MockAgent` determinístico con `MOCK_LLM=1`.
- **Por qué**: el enunciado menciona Agno explícitamente y el caso de uso requiere un agente ligero con tools locales, instrucciones claras y salida estructurada. Agno encaja mejor que una arquitectura grande para esta prueba.
- **Qué me gustó / no me gustó del framework**: me gustó que permite combinar tools e instrucciones en una estructura pequeña. Sinceramente, no hubo nada en especial que no me gustara.
- **Qué descarté**: LangChain/LlamaIndex para este alcance, porque serían más útiles con RAG amplio, múltiples retrievers o workflows complejos. También descarté código casero puro porque el enunciado pedía explícitamente un agente Agno/OpenAI o mock.

### D13 · Modelo elegido + estimación de coste a 5.000 emails/día

- **Modelo**: dejé configurado `gpt-4o-mini` como modelo por defecto de bajo coste para clasificación estructurada de emails cortos. La validación real con API key queda pendiente.
- **Tokens medios por request** (input + output): no los medí con tráfico real. Para estimar, supongo 900 tokens de entrada por email entre instrucciones, contexto y email redactado, y 150 tokens de salida para la respuesta estructurada.
- **Coste por request** (€): aproximación no medida. Tomando precios de modelo mini publicados en USD como referencia y un tipo de cambio aproximado, el orden de magnitud sería alrededor de `0,0012–0,0014 €` por email bajo esos supuestos.
- **Coste mensual estimado** (€): `5.000 emails/día × 30 días = 150.000 emails/mes`. Con 900 input tokens y 150 output tokens por email: 135M input tokens y 22,5M output tokens al mes. Usando como referencia precios mini publicados de `$0.75 / 1M input tokens` y `$4.50 / 1M output tokens`, el coste base sería `$101,25 input + $101,25 output = $202,50/mes`, aproximadamente `185–205 €/mes` según tipo de cambio. Si se pudiera usar Batch API, podría reducirse aproximadamente a la mitad. Esta cifra es orientativa, no coste real medido.

### D14 · Diseño del schema Pydantic

- **Qué hice**: definí esquemas Pydantic v2 para request/response y un enum cerrado de categorías: `technical_issue`, `billing`, `onboarding`, `fraud`, `churn_threat` y `other`.
- **Por qué enum cerrado de categorías**: facilita routing operativo, métricas por categoría, tests reproducibles y dashboards. También reduce respuestas ambiguas del LLM.
- **Por qué cap 300 chars en `reasoning`**: limita coste, evita respuestas largas innecesarias, reduce riesgo de exponer información sensible y fuerza explicaciones operativas breves.
- **Qué descarté**: texto libre como salida principal y categorías abiertas generadas por el LLM. También descarté reasoning largo en la respuesta pública. Para auditoría profunda usaría trazas internas separadas.

### D15 · Estrategia de evaluación antes de producción

- **Qué hice / propondría**: validé técnicamente el flujo con `MOCK_LLM=1`. Antes de producción construiría una evaluación real con API key, datos representativos y revisión humana.
- **Golden set**: lo construiría con soporte/operaciones, incluyendo emails reales o anonimizados por categoría, idioma, urgencia, segmento y casos críticos.
- **LLM-as-judge**: lo usaría solo como apoyo para revisar consistencia de explicaciones o encontrar discrepancias, no como sustituto del golden set humano.
- **Métricas clave**: precision/recall/F1 por categoría, recall de urgencias 4-5, falsos negativos críticos, tasa de escalado humano, latencia p50/p95, tasa de error y coste por 1.000 emails.
- **Qué supuse**: no basta con que pasen tests técnicos, sinó que el modo real debe demostrar calidad, coste y latencia aceptables antes de producción.

### D16 · Mitigación cuando el LLM falla (urgencia 5 clasificada como 2)

- **Qué hice**: añadí guardrails y reglas de escalado para prompt injection y casos críticos en el mock. También dejé `flag_for_human_review` como tool/side-effect para revisión humana.
- **Por qué**: el error más grave sería perder casos críticos, como fraude, amenaza explícita de cancelación o imposibilidad de cobrar. Prefiero escalar de más antes que dejar sin revisar una urgencia real.
- **Qué descarté**: confiar únicamente en la clasificación del LLM para urgencias altas.

---

## Parte 5 · Pregunta-trampa (collusion rings)

### D17 · Honestidad técnica

- **Por qué este problema es difícil**: detectar collusion rings no es una clasificación tabular simple. Requiere analizar relaciones entre merchants, tarjetas, dispositivos, IPs, cuentas bancarias, geografía y patrones temporales. Además, las redes fraudulentas pueden camuflarse como comportamiento legítimo de comercios relacionados.
- **Qué datos pediría**: identificadores tokenizados de tarjeta/cuenta, relaciones merchant-cliente, terminal/dispositivo, IP, geolocalización aproximada, chargebacks, reversals, disputas, timestamps, importes, MCC, ownership/KYC y señales históricas de fraude confirmadas.
- **Qué algoritmos investigaría**: graph analytics, connected components, community detection, PageRank/centrality, detección de anomalías en grafos, modelos temporales, reglas antifraude y, si hay labels, modelos supervisados con features de red.
- **Tiempo realista necesario**: no lo resolvería correctamente en unas horas. Haría una exploración inicial en 1-2 días, un prototipo de features de grafo en 1-2 semanas y una validación seria con fraude/operaciones en varias iteraciones.

---

## Decisiones extra

### D18 · Dependencias y reproducibilidad

- **Qué hice**: mantuve el proyecto ejecutable con `uv`, tests reproducibles y notebooks/outputs versionables solo cuando aportan evidencia de la parte correspondiente.
- **Por qué**: la entrega debe poder ejecutarse por el evaluador con comandos simples y sin depender de mi entorno local.
- **Qué descarté**: subir `.venv`, caches, datos generados localmente o archivos internos de ayuda.
- **Qué supuse**: el evaluador instalará dependencias desde `pyproject.toml`/`uv.lock` y ejecutará tests en un entorno limpio.