# SELF_REVIEW.md — `Fornes Reynes, Josep Gabriel`

---

## P1 · La heurística `merchants_at_risk` no mejora la tasa base

- **Qué falla**: la heurística de riesgo de Parte 1 es interpretable, pero no valida bien como ranking predictivo. En el top 200 merchants, la `Precision@200` queda alrededor de 8,5%, mientras que la tasa global de churn está alrededor de 8,7%. Es decir, la lista priorizada no concentra más churners que la población general.
- **Por qué falla**: los pesos de la heurística se definieron de forma razonada, no aprendida ni validados contra snapshots históricos. Además, el dataset parece tener un único snapshot principal, por lo que no puedo ajustar y validar la señal en períodos distintos. También es posible que parte del churn dependa de factores no observables en las transacciones, como precio, contrato, competencia, soporte o decisiones administrativas.
- **Cómo lo arreglaría con más tiempo**: usaría varios snapshots históricos, validación out-of-time, revisión con negocio y ajuste de pesos con resultados reales. También separaría merchants por segmento/MCC para evitar penalizar comportamientos normales de ciertos tipos de negocio.
- **Impacto en producción**: si se usara tal cual, podría priorizar merchants que no tienen mayor riesgo real que la población general, desperdiciando acciones comerciales o revisiones humanas. Por eso no la presento como predictor validado, sino como señal exploratoria y baseline manual interpretable.

## P2 · La validación del modelo de churn no es out-of-time real

- **Qué falla**: en Parte 3 construyo features temporalmente seguras hasta `reference_date`, pero el split final es estratificado a nivel merchant. No es una validación temporal real contra snapshots futuros.
- **Por qué falla**: el dataset parece estar centrado en un snapshot principal. Sin snapshots posteriores, no puedo medir si el modelo generaliza temporalmente.
- **Cómo lo arreglaría con más tiempo**: pediría varios snapshots mensuales o trimestrales, entrenaría en períodos antiguos y validaría en períodos posteriores. También revisaría drift de features, estabilidad de SHAP y calibración por período.
- **Impacto en producción**: las métricas pueden ser optimistas o inestables. Un modelo que parece útil en un split aleatorio/estratificado puede fallar al aplicarse a meses futuros.

## P3 · Integración real con OpenAI/Agno no validada con API key

- **Qué falla**: la Parte 4 está validada con `MOCK_LLM=1`, pero no probé llamadas reales a OpenAI con API key. Por tanto, no medí calidad real, latencia real, coste real ni comportamiento real del structured output.
- **Por qué falla**: no ejecuté tráfico real contra un proveedor externo durante la entrega. El mock valida contrato, endpoints, guardrails y side-effects, pero no sustituye una prueba semántica del LLM.
- **Cómo lo arreglaría con más tiempo**: probaría el modo real con una API key controlada, mediría errores, timeouts, rate limits, latencia, tokens por request y coste. Además, evaluaría la calidad con un golden set etiquetado.
- **Impacto en producción**: podrían aparecer fallos no detectados por el mock: respuestas mal formadas, diferencias en structured output, costes superiores a lo esperado o baja calidad semántica en casos reales.

---

## Problemas adicionales

### P4 · Las probabilidades del modelo no están bien calibradas

- **Qué falla**: el modelo de Parte 3 debe interpretarse principalmente como ranking de riesgo, no como probabilidad calibrada de churn.
- **Por qué falla**: el target está desbalanceado y se usan estrategias como `class_weight` y `scale_pos_weight`, que pueden mejorar ranking pero distorsionar probabilidades.
- **Cómo lo arreglaría con más tiempo**: calibraría el modelo con Platt scaling o isotonic regression usando un set de validación temporal, y mediría Brier score/calibration curve por segmento.
- **Impacto en producción**: si se interpretan los scores como probabilidades reales, negocio podría tomar decisiones con una confianza incorrecta.

### P5 · Features de reclamos requieren validación temporal/operacional

- **Qué limita**: construí las features de reclamos usando solo reclamaciones con `last_complaint_date <= reference_date`, por lo que las reclamaciones posteriores al snapshot no se usan para entrenar el modelo. Aun así, estas variables aparecen entre las más importantes en SHAP y requieren validación adicional.
- **Por qué importa**: aunque el filtro temporal evita usar fechas futuras de forma directa, necesito confirmar con negocio/data owners cómo se generó `last_complaint_date`, cuándo está disponible en los sistemas y si puede actualizarse retroactivamente. Si esa columna no estuviera disponible en el momento real de scoring, el modelo podría depender de una señal no reproducible en producción.
- **Cómo lo arreglaría con más tiempo**: validaría la definición exacta de la columna, su fecha de disponibilidad y posibles actualizaciones retroactivas. Idealmente reconstruiría estas features desde una tabla histórica de reclamaciones usando un corte temporal explícito en `reference_date`.
- **Impacto en producción**: si la disponibilidad operacional no se valida, el modelo podría mostrar métricas offline demasiado optimistas o depender de una señal que no estaría disponible de forma fiable al hacer scoring.

---

## Lo que sí me salió bien

- Separé observación, limpieza reproducible, decisiones y limitaciones. Eso ayuda a que otra persona pueda auditar el trabajo.
- Fui conservador con leakage: no usé `cancellation_reason`, no usé información posterior a `reference_date` para features predictivas y documenté las variables sensibles.
- La Parte 4 queda reproducible con `MOCK_LLM=1`, por lo que el evaluador puede ejecutar tests y endpoints sin API key externa.