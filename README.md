# Getnet AI Lab Graduate Program 2026 · Take-home solution

Solución del take-home técnico para el AI Lab de Getnet. El repositorio implementa las cuatro partes obligatorias del ejercicio:

1. **Parte 1 · Pandas + EDA**: limpieza, KPIs mensuales, reporte de calidad de datos y ranking heurístico de merchants en riesgo.
2. **Parte 2 · SQL**: queries analíticas para métricas, churn y agregaciones de negocio.
3. **Parte 3 · ML**: modelo de churn a nivel merchant, métricas, interpretabilidad y model card.
4. **Parte 4 · FastAPI + Agno**: API para clasificar reclamaciones de merchants con guardrails, redacción de PII, contexto de merchant y cola de revisión humana.

La documentación de criterio está en:

- `DECISIONS.md`
- `ASSUMPTIONS.md`
- `SELF_REVIEW.md`
- `TOOLS_USED.md`

---

## 1. Requisitos

Probado con:

- Python `>=3.10,<3.14`
- `uv` como gestor de dependencias
- FastAPI + Uvicorn para la API
- `MOCK_LLM=1` para ejecutar tests y API sin depender de una API key externa

Instalación recomendada de `uv` si no está disponible:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Fallback con `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

---

## 2. Setup rápido

Desde la raíz del repositorio:

```bash
uv sync --extra dev
```

Sanity check del entorno:

```bash
uv run python -c "import pandas, sklearn, fastapi, uvicorn, agno, pydantic; print('OK')"
```

También se puede usar:

```bash
make setup
```

---

## 3. Estructura del ZIP entregado

El ZIP final sigue la estructura pedida en el enunciado y contiene únicamente los archivos obligatorios, el código, los tests y los outputs generados:

```text
FornesReynes_JosepGabriel_TakeHome.zip
├── README.md
├── DECISIONS.md
├── ASSUMPTIONS.md
├── SELF_REVIEW.md
├── TOOLS_USED.md
├── .git/
├── pyproject.toml
├── src/
├── tests/
├── outputs/
└── notebooks/
```

Contenido principal:

* `README.md`: instrucciones para arrancar y evaluar esta solución.
* `DECISIONS.md`: decisiones técnicas, trade-offs y criterios usados.
* `ASSUMPTIONS.md`: supuestos adoptados ante ambigüedades del enunciado o del dataset.
* `SELF_REVIEW.md`: revisión crítica de limitaciones, problemas detectados y mejoras futuras.
* `TOOLS_USED.md`: herramientas, LLMs, librerías y documentación consultada.
* `.git/`: historial completo del trabajo.
* `pyproject.toml`: dependencias y configuración del proyecto.
* `src/`: código fuente de las cuatro partes.
* `tests/`: tests añadidos para validar la solución.
* `outputs/`: CSVs, JSONs, modelo y figuras generadas por el código.
* `notebooks`: notebooks usados como apoyo de análisis y explicación.

No se incluyen `.venv/`, `.idea/`, caches, `data/transactions_sample.csv`, `data/_generator.py` ni `templates/`, siguiendo las instrucciones de entrega.

---

## 4. Ejecutar tests

Suite completa:

```bash
MOCK_LLM=1 uv run pytest -v
```

Atajo equivalente:

```bash
make test
```

Tests de la API:

```bash
MOCK_LLM=1 uv run pytest -v tests/test_api.py
```

Atajo:

```bash
make test-api
```

Los tests de la API fuerzan `MOCK_LLM=1`, por lo que no requieren `OPENAI_API_KEY`.

---

## 5. Parte 1 · Pandas + EDA

Archivo principal:

```text
src/parte1_pandas.py
```

Funciones implementadas:

- `load_clean(path)`
- `monthly_kpis(df)`
- `quality_report(df)`
- `merchants_at_risk(df, top_n=200)`

Para regenerar outputs de Parte 1:

```bash
uv run python -m src.parte1_pandas data/transactions_sample.csv
```

Esto genera o actualiza:

```text
outputs/monthly_kpis.csv
outputs/quality_report.json
outputs/merchants_at_risk.csv
outputs/merchants_at_risk_eval.json
```

Decisiones relevantes:

- Parseo explícito de importes en formato local con punto de miles y coma decimal.
- Fechas mixtas tratadas con parser controlado.
- Conservación de columnas `*_raw` para trazabilidad.
- Deduplicación por columnas de negocio normalizadas, no solo por `transaction_id`.
- No se usa `fla_churn90`, `cancellation_reason` ni información posterior a `reference_date` para construir señales predictivas.

La heurística de `merchants_at_risk` se documenta como señal exploratoria, no como predictor validado de producción.

---

## 6. Parte 2 · SQL

Archivo:

```text
src/parte2_sql.sql
```

Incluye las queries pedidas en el enunciado para:

- KPIs agregados por merchant/mes.
- Métricas de churn por snapshot.
- Ranking de merchants y ventanas temporales.
- Consideraciones de particionado y filtro temporal.

Decisiones principales:

- Uso de `transaction_date` como fecha de negocio.
- Uso de intervalos semiabiertos, por ejemplo `[2025-07-01, 2025-10-01)`, para evitar errores con timestamps.
- `reference_date = DATE '2025-09-30'` como snapshot de churn.
- TPV definido como suma de `amount` solo en transacciones `approved`.

---

## 7. Parte 3 · Modelo de churn

Notebook:

```text
src/parte3_modeling.ipynb
```

Artefactos principales:

```text
outputs/model.pkl
outputs/model_card.md
outputs/model_metrics.json
outputs/feature_importance.csv
outputs/feature_importance.png
outputs/calibration_curve.png
outputs/local_shap_explanation.csv
outputs/local_shap_waterfall.png
outputs/local_shap_false_positive_explanation.csv
outputs/local_shap_false_positive_waterfall.png
outputs/sanity_check_no_complaint_metrics.json
```

Resumen de enfoque:

- Dataset de modelado a nivel merchant.
- Exclusión de columnas con riesgo de leakage: `cancellation_reason`, `fla_churn90`, `reference_date`, `dat_process`, identificadores y columnas raw.
- Features temporales construidas solo con información disponible hasta `reference_date`.
- Comparación entre baseline, Logistic Regression y XGBoost.
- Métricas enfocadas en clasificación desbalanceada: ROC-AUC, Average Precision / PR-AUC, Brier score y precision/recall@k.
- Interpretabilidad con SHAP global y local.
- Sanity check eliminando features de reclamos.

Limitación importante: la validación no es out-of-time real porque el dataset parece centrado en un snapshot principal. Por tanto, el modelo debe interpretarse como ranking de riesgo experimental, no como probabilidad calibrada lista para producción.

---

## 8. Parte 4 · API FastAPI + Agno

Directorio:

```text
src/parte4_api/
```

### 8.1 Arranque en modo mock, reproducible y sin coste

```bash
MOCK_LLM=1 uv run uvicorn src.parte4_api.main:app --reload --port 8000
```

Atajo:

```bash
make run
```

### 8.2 Arranque con OpenAI

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"
uv run uvicorn src.parte4_api.main:app --reload --port 8000
```

La integración real con Agno/OpenAI está implementada, pero la validación reproducible de esta entrega se hizo con `MOCK_LLM=1` para evitar dependencia de proveedor externo.

### 8.3 Health check

```bash
curl -s http://localhost:8000/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "model": "mock",
  "version": "0.1.0"
}
```

### 8.4 Clasificación individual

```bash
curl -s -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": 10063716,
    "email_text": "Llevo 3 días sin poder cobrar con el POS. Voy a cancelar la cuenta.",
    "locale": "es"
  }'
```

Respuesta ejemplo:

```json
{
  "merchant_id": 10063716,
  "category": "churn_threat",
  "urgency": 5,
  "requires_human_escalation": true,
  "reasoning": "merchant mentions cancellation risk",
  "merchant_context_used": true,
  "latency_ms": 0
}
```

### 8.5 Clasificación batch

```bash
curl -s -X POST http://localhost:8000/classify/batch \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"merchant_id": 10063716, "email_text": "POS roto, no puedo cobrar", "locale": "es"},
      {"merchant_id": 10063717, "email_text": "Factura incorrecta", "locale": "es"}
    ]
  }'
```

El batch acepta entre 1 y 50 items.

### 8.6 Guardrails y tools

Implementado en `src/parte4_api/agent.py`:

- Detección básica de prompt injection antes de llamar al LLM.
- Redacción básica de PII antes del LLM: email, teléfono y tarjeta.
- Tool `get_merchant_context(merchant_id)`, usando `data/merchants_context.json`.
- Tool `flag_for_human_review(merchant_id, reason)`, que escribe en `outputs/human_review_queue.jsonl`.
- Escalado humano para urgencia alta, amenaza de churn, fraude, prompt injection o reclamaciones repetidas.

Categorías válidas:

```text
technical_issue
billing
onboarding
fraud
churn_threat
other
```

Urgencia válida: entero de `1` a `5`.

---

## 9. Variables de entorno

| Variable | Uso | Valor recomendado para evaluación |
|---|---|---|
| `MOCK_LLM` | Activa agente determinístico sin llamadas externas | `1` |
| `OPENAI_API_KEY` | API key para modo real con OpenAI | solo si se quiere probar modo real |
| `OPENAI_MODEL` | Modelo usado por Agno/OpenAI | `gpt-4o-mini` |

Para evaluación reproducible:

```bash
export MOCK_LLM=1
```

---

## 10. Comandos útiles

```bash
make setup      # instala dependencias con uv
make test       # ejecuta todos los tests con MOCK_LLM=1
make test-api   # ejecuta solo tests de la API
make run        # arranca la API en modo mock
make lint       # ejecuta ruff
make clean      # elimina caches, .venv y artefactos de build
```

Comandos equivalentes sin Makefile:

```bash
uv sync --extra dev
MOCK_LLM=1 uv run pytest -v
MOCK_LLM=1 uv run uvicorn src.parte4_api.main:app --reload --port 8000
```

---

## 11. Validación realizada

La validación reproducible de la entrega cubre:

- Tests unitarios de Parte 1 con datos sintéticos.
- Validación de errores de entrada y columnas obligatorias.
- Tests de `/health`, `/classify` y `/classify/batch`.
- Guardrail de prompt injection.
- Redacción básica de PII.
- Side-effect de escalado humano en `outputs/human_review_queue.jsonl`.
- Límite de 50 elementos en batch.

La API se valida en modo `MOCK_LLM=1`. Esto permite revisar contrato, endpoints, schemas y side-effects sin depender de una API key externa.

---

## 12. Limitaciones conocidas

Las principales limitaciones están detalladas en `SELF_REVIEW.md`. Las más importantes son:

1. La heurística de merchants en riesgo no mejora claramente la tasa base de churn, por lo que no debe usarse como predictor validado.
2. La validación del modelo de churn no es out-of-time real.
3. El modelo debe interpretarse como ranking, no como probabilidad calibrada.
4. La integración real Agno/OpenAI no fue validada con tráfico real ni golden set etiquetado.
5. La redacción de PII es básica y debería ampliarse antes de producción.
6. La cola JSONL de revisión humana es suficiente para el take-home, pero no es una cola robusta de producción.

---

## 13. Empaquetado recomendado para entrega

Antes de crear el ZIP, limpiar caches y entorno virtual:

```bash
rm -rf .venv .pytest_cache .ruff_cache **/__pycache__ build dist *.egg-info
```

Comprobar estado de Git:

```bash
git status
```

Crear ZIP final excluyendo entorno virtual, caches, CSV original y plantillas:

```bash
# Excluye .venv, cache, el CSV original (ya lo tenemos) y el generador interno
zip -r Apellido_Nombre_TakeHome.zip . \
  -x ".venv/*" "**/__pycache__/*" "*.pyc" \
     "data/transactions_sample.csv" "data/_generator.py" "templates/*" \
     "build/*" "dist/*" "*.egg-info/*"
```

---

# `notebooks/`

Esta carpeta contiene notebooks usados como apoyo de análisis y explicación.

## `parte1_eda.ipynb`

Notebook exploratorio usado antes de implementar `src/parte1_pandas.py`. Sirve para revisar formatos, nulos, duplicados, valores categóricos, posibles leakage y patrones temporales.

No es la fuente productiva de limpieza, la lógica reproducible vive en `src/parte1_pandas.py`.

---

## 14. Notas de lectura para el evaluador

- `DECISIONS.md` explica el razonamiento técnico, trade-offs, leakage, métricas y decisiones de API/agente.
- `ASSUMPTIONS.md` enumera ambigüedades del enunciado y supuestos adoptados.
- `SELF_REVIEW.md` recoge errores propios, limitaciones y cómo los mitigaría antes de producción.
- `TOOLS_USED.md` declara el uso de herramientas externas/LLMs.
- `src/parte4_api/README.md` contiene una explicación más específica de la API.
