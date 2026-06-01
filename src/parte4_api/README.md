# Parte 4 · API de clasificación de reclamaciones

Esta API clasifica emails de reclamaciones de merchants usando FastAPI y un agente Agno. Puede ejecutarse con OpenAI o en modo determinístico offline mediante `MOCK_LLM=1`.

## Arquitectura

```
parte4_api/
├── main.py        ← FastAPI app + endpoints + dependency injection
├── agent.py       ← agente Agno + tools + guardrails + PII redaction
├── schemas.py     ← Pydantic v2 models (request/response)
└── README.md      ← este archivo
```

## Cómo arrancar (el evaluador ejecutará exactamente esto)

```bash
# Opción A · con clave OpenAI propia
export OPENAI_API_KEY=sk-...
uvicorn src.parte4_api.main:app --reload --port 8000

# Opción B · sin clave (LLM mockeado, determinístico)
export MOCK_LLM=1
uvicorn src.parte4_api.main:app --reload --port 8000
```

## Endpoints

### `GET /health`

```bash
curl -s http://localhost:8000/health | jq
```

Respuesta:
```json
{ "status": "ok", "model": "gpt-4o-mini-or-mock", "version": "0.1.0" }
```

### `POST /classify`

```bash
curl -s -X POST http://localhost:8000/classify \
  -H 'Content-Type: application/json' \
  -d '{
    "merchant_id": 10063716,
    "email_text": "Llevo 3 días sin poder cobrar con el POS, voy a cancelar la cuenta.",
    "locale": "es"
  }' | jq
```

Respuesta:
```json
{
  "merchant_id": 10063716,
  "category": "churn_threat",
  "urgency": 4,
  "requires_human_escalation": true,
  "reasoning": "...",
  "merchant_context_used": false,
  "latency_ms": 423
}
```

### `POST /classify/batch`

```bash
curl -s -X POST http://localhost:8000/classify/batch \
  -H 'Content-Type: application/json' \
  -d '{"items":[
    {"merchant_id":10063716,"email_text":"POS roto","locale":"es"},
    {"merchant_id":10063717,"email_text":"Factura incorrecta","locale":"es"}
  ]}' | jq
```

## Tests

```bash
MOCK_LLM=1 pytest -v tests/test_api.py
```

Cobertura mínima: `test_health`, `test_classify_happy_path`, `test_classify_prompt_injection`, `test_classify_invalid_input`, `test_batch_concurrency`.

## Decisiones técnicas documentadas

Las decisiones principales están recogidas en `DECISIONS.md`, incluyendo:

- Por qué Agno (vs LangChain/LlamaIndex).
- Modelo elegido + estimación de coste mensual procesando 5.000 emails/día.
- Trade-offs del schema Pydantic (¿por qué enum cerrado? ¿por qué cap 300 chars en `reasoning`?).
- Cómo evaluarías la calidad antes de producción (golden set, LLM-as-judge, métricas).
- Mitigación cuando el LLM clasifica mal una urgencia 5 como urgencia 2.

## Guardrails implementados

- **Prompt injection**: patrones detectados en `agent.detect_prompt_injection`.
- **PII redaction**: `agent.redact_pii` redacta email/teléfono/tarjeta antes de mandar al LLM.
- **Escalado humano**: tool `flag_for_human_review` persiste en `outputs/human_review_queue.jsonl`.

## Limitaciones conocidas

- El modo mock no reemplaza una evaluación real de calidad del LLM.
- Las reglas del mock solo existen para tests offline.
- Antes de producción haría un golden set etiquetado, medición por categoría, revisión de falsos negativos de urgencia alta y calibración de criterios de escalado.

## Alcance de validación

Para esta entrega he validado la API en modo `MOCK_LLM=1`.

Esto permite comprobar de forma reproducible:

- contrato de entrada/salida con Pydantic;
- endpoints `/health`, `/classify` y `/classify/batch`;
- guardrail de prompt injection;
- redacción básica de PII;
- uso de contexto de merchant;
- side-effect de escalado humano;
- ejecución de tests sin depender de una API key externa.

La integración real con Agno/OpenAI está implementada, pero no ha sido validada con una API key real en esta entrega. Antes de producción, probaría el flujo completo con un proveedor real, mediría calidad sobre un golden set etiquetado y revisaría latencia, coste, errores y rate limits.
