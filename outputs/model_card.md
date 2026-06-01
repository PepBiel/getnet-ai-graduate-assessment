# Model card · Parte 3

## Objetivo

Predecir `fla_churn90` a nivel merchant usando señales disponibles hasta `reference_date`.

## Grano del dataset

Una fila por merchant. Las transacciones se agregan a features de comportamiento antes del snapshot.

## Target

`fla_churn90`: 1 si el merchant churneó en los 90 días posteriores al snapshot.

## Modelo seleccionado

`xgboost`

## Features usadas

### Numéricas

['recent_tpv', 'previous_tpv', 'tpv_drop_ratio', 'recent_n_tx', 'previous_n_tx', 'tx_drop_ratio', 'recent_approval_rate', 'previous_approval_rate', 'approval_rate_drop', 'recent_bad_status_rate', 'previous_bad_status_rate', 'recent_pct_ecom_tpv', 'previous_pct_ecom_tpv', 'recent_pct_pix_tpv', 'previous_pct_pix_tpv', 'days_since_last_tx', 'median_days_between_tx', 'days_since_last_complaint_safe']

### Categóricas

['segment', 'mcc', 'has_safe_tx_history', 'has_safe_complaint']

## Features descartadas

- `cancellation_reason`: posible leakage post-evento.
- `last_complaint_date` directa: puede contener información posterior al snapshot.
- `merchant_id`: identificador, riesgo de memorización.
- `transaction_id`: identificador transaccional.
- `transaction_date` directa: se usa solo para construir agregados temporales seguros.
- `reference_date` directa: snapshot, no señal de comportamiento.
- `dat_process`: fecha operativa/procesamiento.
- columnas `*_raw`: trazabilidad, no features.

## Métricas

                          model  roc_auc  average_precision  brier_score  positive_rate_test  recall_at_1pct  precision_at_1pct  recall_at_5pct  precision_at_5pct  recall_at_10pct  precision_at_10pct  ap_lift_vs_baseline  brier_delta_vs_baseline
baseline_constant_positive_rate 0.500000           0.087340     0.079712             0.08734             NaN                NaN             NaN                NaN              NaN                 NaN             1.000000                 0.000000
            logistic_regression 0.617428           0.113666     0.233977             0.08734        0.013761               0.12        0.059633              0.104          0.12844               0.112             1.301429                 0.154265
                        xgboost 0.601030           0.115016     0.212172             0.08734        0.013761               0.12        0.045872              0.080          0.12844               0.112             1.316876                 0.132461

## Interpretabilidad

Se calcularon importancias globales con SHAP sobre una muestra del test set. Las importancias indican asociación con la predicción, no causalidad.

Top-5 features:

                            feature  mean_abs_shap
      cat__has_safe_complaint_False       0.351519
                  num__previous_tpv       0.156565
num__days_since_last_complaint_safe       0.147177
            num__days_since_last_tx       0.143391
        num__median_days_between_tx       0.100961

## Sanity check sin features de reclamos

También entrené una versión de XGBoost sin `has_safe_complaint` ni `days_since_last_complaint_safe`. Al quitarlas, baja la Average Precision y el ROC-AUC, lo que sugiere que aportan señal. Aun así, estas variables deben validarse con negocio porque proceden de una columna que ya se había identificado como sensible a leakage temporal.

## Interpretabilidad local

Además de la importancia global, generé explicaciones locales con SHAP:

- un true positive de alto score, para entender un caso donde el modelo asigna alto riesgo y el merchant efectivamente churneó
- un false positive de alto score, para revisar qué señales pueden generar falsas alarmas.

En las explicaciones revisé tanto contribuciones positivas como negativas. Las contribuciones positivas aumentan el score de churn del merchant, mientras que las negativas lo reducen. Esta separación ayuda a entender que una predicción no depende de una única variable, sino del balance entre señales de riesgo y señales que moderan ese riesgo.

Estas explicaciones ayudan a auditar el comportamiento del modelo caso a caso. No sustituyen la evaluación global ni implican causalidad.

## Limitaciones

- Si solo existe un snapshot principal, el split no es una validación temporal real entre snapshots.
- La validación es estratificada a nivel merchant, no out-of-time.
- Las features se construyen evitando información posterior a `reference_date`, pero la robustez debería validarse en otro periodo.
- El score del modelo no debe usarse directamente para decisiones automáticas sin calibración y validación de negocio.
- SHAP indica asociación con la predicción, no causalidad.
- Las probabilidades no están necesariamente calibradas, el modelo debe interpretarse principalmente como ranking de riesgo.
- Las features relacionadas con reclamos aparecen entre las más importantes, por lo que deberían validarse con negocio antes de usarse en producción.
- Los false positives deben revisarse con negocio: pueden ser falsas alarmas reales o merchants con señales de deterioro que finalmente no churnearon en la ventana de 90 días.
