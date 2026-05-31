-- =============================================================================
-- Parte 2 · SQL sobre warehouse (10 pts)
-- =============================================================================
-- Estilo esperado: Spark SQL / Databricks SQL (equivalente a ANSI con LAG, etc.)
-- No necesitas ejecutar las queries. Escríbelas y comenta supuestos.
--
-- Esquema:
--   merchants(merchant_id, country, mcc, onboarding_date, segment)
--   transactions(transaction_id, merchant_id, transaction_date, amount, status,
--                channel, dat_process)
--   churn_labels(merchant_id, reference_date, fla_churn90)
--
-- Documenta cualquier supuesto en `DECISIONS.md`.
-- =============================================================================

-- Supuestos generales:
-- 1. merchants tiene grano de una fila por merchant.
-- 2. transactions tiene grano de una fila por transacción.
-- 3. churn_labels tiene grano de una fila por merchant y reference_date.
-- 4. transaction_date es la fecha de negocio para agregaciones temporales.
-- 5. dat_process es fecha de procesamiento/partición; puede ayudar al pruning,
--    pero no sustituye a transaction_date para definir periodos de negocio.
-- 6. TPV se calcula como suma de amount solo para status = 'approved'.
-- 7. approval_rate se calcula como transacciones approved / total transacciones.
-- 8. mcc se trata como categoría.
-- 9. Q3 2025 se interpreta como intervalo semiabierto: [2025-07-01, 2025-10-01).

-- -----------------------------------------------------------------------------
-- Q1 (3 pts) — Top 10 merchants brasileños por TPV aprobado de Q3 2025.
--
-- Output esperado:
--   merchant_id
--   tpv
--   approval_rate
--   mcc
--
-- Supuesto: interpreto Q3 2025 como [2025-07-01, 2025-10-01).
-- Uso intervalo semiabierto en lugar de BETWEEN para evitar problemas si
-- transaction_date tuviera componente horario.
-- -----------------------------------------------------------------------------

SELECT
    transactions.merchant_id,
    SUM(CASE WHEN LOWER(transactions.status) = 'approved' THEN transactions.amount ELSE 0 END) AS tpv,
    SUM(CASE WHEN LOWER(transactions.status) = 'approved' THEN 1 ELSE 0 END) / COUNT(*) AS approval_rate,
    merchants.mcc
FROM transactions
JOIN merchants
    ON transactions.merchant_id = merchants.merchant_id
WHERE merchants.country = 'BR'
    AND transactions.transaction_date >= DATE '2025-07-01'
    AND transactions.transaction_date < DATE '2025-10-01'
GROUP BY
    transactions.merchant_id,
    merchants.mcc
ORDER BY
    tpv DESC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- Q2 (3 pts) — % de merchants con fla_churn90 = 1 por (country, segment)
-- a reference_date = '2025-09-30'. Solo segmentos con >= 100 merchants.
--
-- Calculo churn a nivel merchant, no a nivel transacción.
-- Asumo una única fila por merchant_id y reference_date en churn_labels.
-- Si hubiese duplicados, deduplicaría churn_labels antes del join.
-- -----------------------------------------------------------------------------

WITH churn_by_segment AS (
    SELECT
        merchants.country,
        merchants.segment,
        COUNT(DISTINCT merchants.merchant_id) AS n_merchants,
        COUNT(DISTINCT CASE
            WHEN churn_labels.fla_churn90 = 1 THEN merchants.merchant_id
        END) AS n_churned_merchants
    FROM merchants
    JOIN churn_labels
        ON merchants.merchant_id = churn_labels.merchant_id
    WHERE churn_labels.reference_date = DATE '2025-09-30'
    GROUP BY
        merchants.country,
        merchants.segment
)

SELECT
    country,
    segment,
    n_merchants,
    n_churned_merchants,
    n_churned_merchants / n_merchants AS churn_rate
FROM churn_by_segment
WHERE n_merchants >= 100
ORDER BY
    churn_rate DESC;

-- -----------------------------------------------------------------------------
-- Q3 (3 pts) — Por merchant, TPV mensual 2025 y TPV mismo mes año anterior (YoY).
--
-- Comparo cada mes de 2025 contra el mismo mes de 2024.
-- Si no existe TPV del año anterior, devuelvo 0.
-- -----------------------------------------------------------------------------

WITH monthly_tpv AS (
    SELECT
        merchant_id,
        DATE_TRUNC('month', transaction_date) AS month,
        SUM(CASE WHEN LOWER(status) = 'approved' THEN amount ELSE 0 END) AS tpv
    FROM transactions
    WHERE transaction_date >= DATE '2024-01-01'
      AND transaction_date < DATE '2026-01-01'
    GROUP BY
        merchant_id,
        DATE_TRUNC('month', transaction_date)
)

SELECT
    cur.merchant_id,
    cur.month,
    cur.tpv AS tpv,
    COALESCE(prev.tpv, 0) AS tpv_same_month_previous_year
FROM monthly_tpv cur
LEFT JOIN monthly_tpv prev
    ON cur.merchant_id = prev.merchant_id
   AND prev.month = ADD_MONTHS(cur.month, -12)
WHERE cur.month >= DATE '2025-01-01'
  AND cur.month < DATE '2026-01-01'
ORDER BY
    cur.merchant_id,
    cur.month;


-- -----------------------------------------------------------------------------
-- Q4 (1 pt) — En 2 líneas: ¿qué ventaja te da que `transactions` esté
-- particionada por `dat_process` al hacer la Q1?
-- -----------------------------------------------------------------------------
-- Si filtramos también por dat_process de forma alineada con Q3 2025, Databricks puede hacer partition pruning y leer menos particiones.
-- transaction_date define el periodo de negocio y dat_process es solo un filtro técnico auxiliar para reducir I/O, tiempo y coste.