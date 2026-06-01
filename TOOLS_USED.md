# TOOLS_USED.md — `Fornes Reynes, Josep Gabriel`

---

## LLMs y asistentes de código

| Herramienta | Versión / modelo | Para qué la usé                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | % aproximado del código |
|---|------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------:|
| ChatGPT | GPT-5.5 Thinking | Contrastar razonamiento técnico, revisar supuestos/limitaciones, ordenar documentación y mejorar redacción de ideas propias. También lo usé como apoyo de investigación inicial para conceptos de negocio y economía que no dominaba por mi perfil informático, como KPIs, TPV, churn, criterios de coste de API y posibles enfoques para la pregunta 5. Las respuestas se contrastaron después con documentación oficial, fuentes fiables y los resultados obtenidos en el proyecto.                                  |                  15-20% |
| Codex | GPT-5.5 High     | Apoyo controlado para implementar cambios concretos, depurar errores, estructurar funciones y revisar entorno/dependencias.                                                                                                                                                                                                                                                                                                                                                                                            |                  20-25% |

No he incluido texto ni código sin entenderlo ni sin comprobar que reflejaba lo que quería hacer.

---

## IDE / editor

- **Editor**: PyCharm / entorno local en Windows.
- **Plugins relevantes**: soporte de Python, notebooks/Jupyter y control de versiones Git.
- **Terminal / entorno**: PowerShell y `uv` para gestionar entorno, dependencias y ejecución de tests.

---

## Librerías añadidas a `pyproject.toml`

> Incluyo las librerías principales añadidas o usadas explícitamente sobre el starter para resolver las partes avanzadas. Algunas ya podían aparecer sugeridas por el proyecto, pero las declaro porque forman parte de la solución final.

| Librería | Versión | Por qué la añadí / usé |
|---|---|---|
| `xgboost` | fijada en `pyproject.toml` / `uv.lock` | Entrenar un segundo modelo tabular no lineal en Parte 3 y compararlo contra Logistic Regression. |
| `shap` | fijada en `pyproject.toml` / `uv.lock` | Interpretabilidad global y local del modelo final en Parte 3. |
| `matplotlib` | fijada en `pyproject.toml` / `uv.lock` | Visualizaciones de correlación, importancia de features, calibración y SHAP. |
| `joblib` | fijada en `pyproject.toml` / `uv.lock` | Persistir el pipeline entrenado de Parte 3 en `outputs/model.pkl`. |
| `fastapi` | fijada en `pyproject.toml` / `uv.lock` | Implementar la API de Parte 4. |
| `uvicorn` | fijada en `pyproject.toml` / `uv.lock` | Servir la API localmente. |
| `agno` | fijada en `pyproject.toml` / `uv.lock` | Implementar el agente solicitado en Parte 4. |
| `openai` | fijada en `pyproject.toml` / `uv.lock` | Provider previsto para el agente real de Parte 4. No validé llamadas reales con API key. |
| `pytest` | fijada en dependencias de desarrollo | Ejecutar tests de Parte 1 y Parte 4. |
| `httpx` / `fastapi.testclient` | fijada en dependencias de desarrollo | Tests de endpoints FastAPI. |

---

## Documentación / recursos consultados

- <https://fastapi.tiangolo.com/>: para estructura de endpoints y uso de `TestClient`.
- <https://docs.pydantic.dev/latest/>: para modelos Pydantic v2, validaciones y configuración estricta.
- <https://docs.agno.com/>: para revisar cómo estructurar un agente con tools y salida estructurada.
- <https://platform.openai.com/docs>: para revisar integración general con proveedor OpenAI.
- <https://openai.com/api/pricing/>: para estimación orientativa de coste mensual. No es coste medido.
- <https://scikit-learn.org/stable/>: para `Pipeline`, `ColumnTransformer`, métricas y split estratificado.
- <https://xgboost.readthedocs.io/>: para configuración básica de `XGBClassifier`.
- <https://shap.readthedocs.io/>: para interpretación global/local con SHAP.
- <https://pandas.pydata.org/docs/>: para operaciones de limpieza, agregación y parsing de fechas/importes.
- <https://stripe.com/resources/more/total-payment-value-tpv-what-it-means-why-it-matters-and-how-to-use-it-wisely>: para entender TPV como volumen total de pagos procesados y su uso en métricas de negocio de pagos.
- <https://www.ibm.com/think/topics/customer-churn>: para revisar el concepto de churn desde una perspectiva de negocio, retención y analítica de clientes.

---

## Reflexión rápida

Los LLMs me ayudaron a contrastar razonamientos, ordenar documentación, mejorar la redacción de mis propias ideas y resolver dudas puntuales de entorno, dependencias y errores. No delegué decisiones técnicas a ciegas: los supuestos, limitaciones, problemas detectados y conclusiones salieron de mi análisis del enunciado, los datos y los resultados.

También usé LLMs como apoyo inicial para entender conceptos de negocio y pagos que no dominaba por mi perfil informático, como KPIs, TPV, churn, o estimación de costes de API. Antes de incorporarlos a la solución, contrasté las explicaciones con documentación oficial o fuentes reconocidas como Stripe, IBM y OpenAI Pricing.

Sí detecté respuestas plausibles pero incorrectas o demasiado optimistas, por ejemplo al proponer usar variables con posible leakage, interpretar métricas como si fueran más fuertes de lo que eran o asumir que una integración real estaba validada sin haberla probado. Lo verifiqué revisando los datos, ejecutando notebooks/tests, comprobando outputs y documentando explícitamente las limitaciones antes de incluir cualquier cambio.