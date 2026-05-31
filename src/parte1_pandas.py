"""
Parte 1 · Análisis exploratorio en pandas (15 pts)
==================================================

Implementa las 4 funciones que aparecen abajo. Lee el `STATEMENT.md` antes de
empezar para entender los requisitos y la rúbrica.

Reglas:
- Código vectorizado. NO loops sobre filas.
- Type hints en las firmas públicas.
- Documenta tus decisiones en `DECISIONS.md`, no aquí.
- El CSV tiene problemas a propósito. Encontrarlos forma parte del test.

Ejecuta con:
    python -m src.parte1_pandas data/transactions_sample.csv

(o adapta el `if __name__ == "__main__"` a tu gusto)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


# -----------------------------------------------------------------------------
# 1.1  load_clean
# -----------------------------------------------------------------------------
def load_clean(path: str | Path) -> pd.DataFrame:
    """
    Carga el CSV y devuelve un DataFrame listo para análisis.

    La limpieza convierte tipos y normaliza campos sin aplicar decisiones
    predictivas globales. Conserva columnas `*_raw` para trazabilidad, no
    elimina `cancellation_reason` ni `last_complaint_date`, no filtra
    transacciones posteriores a `reference_date`, no elimina outliers y no usa
    `fla_churn90` para decidir que filas conservar.

    Las decisiones completas quedan documentadas en `DECISIONS.md` y los
    supuestos en `ASSUMPTIONS.md`.

    Args:
        path: ruta al CSV.

    Returns:
        DataFrame limpio.
    """
    csv_path = Path(path)
    df = pd.read_csv(csv_path, dtype="string")
    df.columns = df.columns.str.strip()
    audit: dict[str, Any] = {"n_rows_raw": int(len(df))}

    required_columns = {
        "transaction_id",
        "merchant_id",
        "transaction_date",
        "amount",
        "status",
        "channel",
        "reference_date",
        "fla_churn90",
    }
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    for column in ["amount", "transaction_date", "reference_date", "last_complaint_date", "dat_process"]:
        if column in df.columns:
            df[f"{column}_raw"] = df[column]

    amount_text = df["amount"].str.strip().replace({"": pd.NA})
    amount_numeric_text = (
        amount_text
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    amount_missing_raw = amount_text.isna()
    df["amount"] = pd.to_numeric(amount_numeric_text, errors="coerce")
    amount_parse_failure = amount_text.notna() & df["amount"].isna()

    audit["amount_missing_raw"] = int(amount_missing_raw.sum())
    audit["amount_parse_failures"] = int(amount_parse_failure.sum())

    def _parse_mixed_date(series: pd.Series) -> pd.Series:
        text = series.astype("string").str.strip().replace({"": pd.NA})
        iso_mask = text.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
        dmy_mask = text.str.match(r"^\d{2}/\d{2}/\d{4}$", na=False)
        parsed_iso = pd.to_datetime(text.where(iso_mask), format="%Y-%m-%d", errors="coerce")
        parsed_dmy = pd.to_datetime(text.where(dmy_mask), format="%d/%m/%Y", errors="coerce")
        parsed_fallback = pd.to_datetime(text.where(~(iso_mask | dmy_mask)), errors="coerce")
        return parsed_iso.fillna(parsed_dmy).fillna(parsed_fallback)

    for date_column in ["transaction_date", "reference_date", "last_complaint_date", "dat_process"]:
        if date_column in df.columns:
            raw_missing = int(df[f"{date_column}_raw"].isna().sum())
            df[date_column] = _parse_mixed_date(df[date_column])
            audit[f"{date_column}_parse_failures"] = int(df[date_column].isna().sum()) - raw_missing

    for id_column in ["transaction_id", "merchant_id", "fla_churn90"]:
        if id_column in df.columns:
            df[id_column] = pd.to_numeric(df[id_column], errors="coerce").astype("Int64")

    for category_column in ["status", "channel", "segment", "cancellation_reason"]:
        if category_column in df.columns:
            normalized = df[category_column].astype("string").str.strip()
            if category_column in {"status", "channel"}:
                normalized = normalized.str.lower()
            df[category_column] = normalized.replace({"": pd.NA})

    if "mcc" in df.columns:
        df["mcc"] = df["mcc"].astype("string").str.strip().replace({"": pd.NA})

    raw_columns = {column for column in df.columns if column.endswith("_raw")}
    dedup_columns = [column for column in df.columns if column != "transaction_id" and column not in raw_columns]
    duplicate_mask = df.duplicated(subset=dedup_columns, keep="first")
    audit["business_duplicate_rows_removed"] = int(duplicate_mask.sum())
    df = df.loc[~duplicate_mask].copy()

    audit["n_rows_clean"] = int(len(df))
    df.attrs["load_clean_audit"] = audit
    return df


# -----------------------------------------------------------------------------
# 1.2  monthly_kpis
# -----------------------------------------------------------------------------
def monthly_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    KPIs mensuales por merchant. Una fila por (merchant_id, month).

    Columnas de salida:
      - merchant_id
      - month               (primer día del mes, dtype datetime64[ns])
      - tpv                 (suma de amount para status == 'approved')
      - approval_rate       (% transacciones aprobadas sobre total)
      - pct_ecom            (% del TPV que viene del canal 'ecom')
      - n_tx                (número de transacciones del mes)

    Vectorizado. Sin loops.

    Args:
        df: DataFrame ya limpio (output de load_clean).

    Returns:
        DataFrame con los KPIs.
    """
    required_columns = {
        "merchant_id",
        "transaction_date",
        "amount",
        "status",
        "channel",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns for monthly_kpis: {sorted(missing_columns)}"
        )

    work = df.copy()
    work = work[work["merchant_id"].notna() & work["transaction_date"].notna()].copy()

    work["month"] = work["transaction_date"].dt.to_period("M").dt.to_timestamp()

    is_approved = work["status"].eq("approved")
    is_ecom = work["channel"].eq("ecom")

    work["approved_amount"] = work["amount"].where(is_approved, 0.0)
    work["approved_ecom_amount"] = work["amount"].where(is_approved & is_ecom, 0.0)
    work["approved_tx"] = is_approved.astype(int)

    grouped = (
        work.groupby(["merchant_id", "month"], as_index=False)
        .agg(
            tpv=("approved_amount", "sum"),
            approved_tx=("approved_tx", "sum"),
            ecom_tpv=("approved_ecom_amount", "sum"),
            n_tx=("merchant_id", "size"),
        )
    )

    grouped["approval_rate"] = grouped["approved_tx"] / grouped["n_tx"]
    grouped["pct_ecom"] = (
        grouped["ecom_tpv"]
        .div(grouped["tpv"])
        .where(grouped["tpv"] > 0, 0.0)
        .fillna(0.0)
    )

    result = grouped[
        ["merchant_id", "month", "tpv", "approval_rate", "pct_ecom", "n_tx"]
    ].copy()
    return result.sort_values(["merchant_id", "month"]).reset_index(drop=True)


# -----------------------------------------------------------------------------
# 1.3  quality_report
# -----------------------------------------------------------------------------
def quality_report(df: pd.DataFrame) -> dict[str, Any]:
    """
    Devuelve un reporte de calidad de datos con al menos 5 problemas detectados.

    Estructura esperada:
        {
          "issues": [
            {
              "column": "<nombre>",
              "rows_affected": <int>,
              "impact": "<descripción del impacto en análisis/modelo>",
              "fix": "<cómo lo resolverías>",
            },
            ...
          ],
          "summary": {
            "n_rows": <int>,
            "n_cols": <int>,
            "n_issues": <int>,
          }
        }
    """
    issues: list[dict[str, Any]] = []
    audit = df.attrs.get("load_clean_audit", {}) or {}

    def add_issue(
        column: str,
        rows_affected: int,
        impact: str,
        fix: str,
    ) -> None:
        """Añade un problema solo si afecta al menos a una fila."""
        rows_affected = int(rows_affected)
        if rows_affected <= 0:
            return

        issues.append(
            {
                "column": column,
                "rows_affected": rows_affected,
                "impact": impact,
                "fix": fix,
            }
        )

    n_rows = int(len(df))
    n_cols = int(df.shape[1])

    # ------------------------------------------------------------------
    # Calidad de amount
    # ------------------------------------------------------------------
    if "amount" in df.columns:
        amount_missing = int(df["amount"].isna().sum())

        add_issue(
            column="amount",
            rows_affected=amount_missing,
            impact=(
                "Los importes ausentes no pueden contribuir al TPV y pueden "
                "infraestimar el volumen del merchant, especialmente si la "
                "transacción está aprobada."
            ),
            fix=(
                "No imputar importes de forma silenciosa. Mantenerlos como "
                "missing para el cálculo de KPIs, reportar el problema y "
                "validar con el origen de datos por qué faltan importes."
            ),
        )

    if {"amount", "status"}.issubset(df.columns):
        approved_amount_missing = int(
            (df["amount"].isna() & df["status"].eq("approved")).sum()
        )

        add_issue(
            column="amount",
            rows_affected=approved_amount_missing,
            impact=(
                "Existen transacciones aprobadas con amount ausente. Esto es "
                "especialmente relevante porque esas operaciones deberían "
                "contribuir al TPV, pero no pueden hacerlo al no tener importe "
                "informado."
            ),
            fix=(
                "No imputar importes sin una regla de negocio. Reportar estos "
                "casos y revisar el origen de datos para entender por qué hay "
                "operaciones aprobadas sin importe."
            ),
        )

    if "amount_raw" in df.columns and "amount" in df.columns:
        amount_raw_text = df["amount_raw"].astype("string").str.strip()
        amount_raw_text = amount_raw_text.replace({"": pd.NA})
        amount_parse_failures = int(
            (amount_raw_text.notna() & df["amount"].isna()).sum()
        )
    else:
        amount_parse_failures = int(audit.get("amount_parse_failures", 0))

    add_issue(
        column="amount",
        rows_affected=amount_parse_failures,
        impact=(
            "Existen valores no vacíos de amount que no se pudieron convertir "
            "a numérico. Esto afecta directamente al TPV y a cualquier feature "
            "basada en importes."
        ),
        fix=(
            "Parsear amount de forma explícita usando el formato BR/ES "
            "observado y revisar cualquier valor que siga sin poder convertirse."
        ),
    )

    if "amount" in df.columns:
        amount_non_null = df["amount"].dropna()

        if not amount_non_null.empty:
            q1 = amount_non_null.quantile(0.25)
            q3 = amount_non_null.quantile(0.75)
            iqr = q3 - q1
            upper_bound = q3 + 1.5 * iqr

            high_amount_rows = int((df["amount"] > upper_bound).sum())

            add_issue(
                column="amount",
                rows_affected=high_amount_rows,
                impact=(
                    "La distribución de amount es muy asimétrica y existen "
                    "importes altos respecto al rango intercuartílico. No los "
                    "trato automáticamente como errores, pero pueden afectar "
                    "agregaciones y modelos sensibles a valores extremos."
                ),
                fix=(
                    "No eliminar automáticamente. Revisar reglas de negocio "
                    "por segmento/MCC y considerar transformaciones robustas "
                    "como percentiles, winsorization o log1p en modelado."
                ),
            )

    # ------------------------------------------------------------------
    # Fechas mixtas y fallos de parseo
    # ------------------------------------------------------------------
    if "transaction_date_raw" in df.columns:
        tx_raw = df["transaction_date_raw"].astype("string").str.strip()
        iso_mask = tx_raw.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
        dmy_mask = tx_raw.str.match(r"^\d{2}/\d{2}/\d{4}$", na=False)
        other_mask = tx_raw.notna() & ~(iso_mask | dmy_mask)

        n_formats = int(iso_mask.any()) + int(dmy_mask.any()) + int(other_mask.any())
        mixed_format_rows = int(dmy_mask.sum() + other_mask.sum())

        if n_formats > 1:
            add_issue(
                column="transaction_date",
                rows_affected=mixed_format_rows,
                impact=(
                    "transaction_date aparece en más de un formato raw. Asumir "
                    "un único formato podría provocar pérdida de filas o fechas "
                    "mal parseadas."
                ),
                fix=(
                    "Usar un parseo explícito multi-formato y registrar los "
                    "fallos de parseo, como se hace en load_clean."
                ),
            )

    for date_column in [
        "transaction_date",
        "reference_date",
        "last_complaint_date",
        "dat_process",
    ]:
        raw_column = f"{date_column}_raw"

        if raw_column in df.columns and date_column in df.columns:
            raw_text = df[raw_column].astype("string").str.strip()
            raw_text = raw_text.replace({"": pd.NA})
            parse_failures = int((raw_text.notna() & df[date_column].isna()).sum())
        else:
            parse_failures = int(audit.get(f"{date_column}_parse_failures", 0))

        add_issue(
            column=date_column,
            rows_affected=parse_failures,
            impact=(
                f"Hay valores no vacíos en {date_column} que no se pudieron "
                "parsear como fecha. Esto puede afectar agregaciones mensuales, "
                "validaciones temporales o construcción de features respecto "
                "al snapshot."
            ),
            fix=(
                "Mantener esos valores como missing, reportarlos y validar con "
                "el data owner cuáles son los formatos de fecha aceptados."
            ),
        )

    # ------------------------------------------------------------------
    # Duplicados de negocio detectados por load_clean
    # ------------------------------------------------------------------
    duplicate_rows_removed = int(audit.get("business_duplicate_rows_removed", 0))

    if duplicate_rows_removed == 0 and "transaction_id" in df.columns:
        raw_columns = {column for column in df.columns if column.endswith("_raw")}
        dedup_columns = [
            column
            for column in df.columns
            if column != "transaction_id" and column not in raw_columns
        ]

        if dedup_columns:
            duplicate_rows_removed = int(
                df.duplicated(subset=dedup_columns, keep="first").sum()
            )

    add_issue(
        column="transaction_id",
        rows_affected=duplicate_rows_removed,
        impact=(
            "Los duplicados de negocio pueden inflar TPV, número de "
            "transacciones y métricas de actividad aunque transaction_id sea "
            "único."
        ),
        fix=(
            "Deduplicar usando columnas de negocio normalizadas, no solo "
            "transaction_id, y conservar el número de filas eliminadas en la "
            "auditoría de load_clean."
        ),
    )

    # ------------------------------------------------------------------
    # Coherencia temporal respecto a reference_date
    # ------------------------------------------------------------------
    if {"transaction_date", "reference_date"}.issubset(df.columns):
        future_tx_mask = (
            df["transaction_date"].notna()
            & df["reference_date"].notna()
            & (df["transaction_date"] > df["reference_date"])
        )

        add_issue(
            column="transaction_date",
            rows_affected=int(future_tx_mask.sum()),
            impact=(
                "Existen transacciones posteriores a reference_date, que se "
                "interpreta como snapshot del análisis. Pueden ser válidas para "
                "análisis descriptivo, pero no deberían usarse como información "
                "disponible en el snapshot para predecir churn."
            ),
            fix=(
                "No eliminarlas globalmente en load_clean. Aplicar de forma "
                "explícita el filtro transaction_date <= reference_date al "
                "construir features predictivas."
            ),
        )

    if {"last_complaint_date", "reference_date"}.issubset(df.columns):
        future_complaint_mask = (
            df["last_complaint_date"].notna()
            & df["reference_date"].notna()
            & (df["last_complaint_date"] > df["reference_date"])
        )

        add_issue(
            column="last_complaint_date",
            rows_affected=int(future_complaint_mask.sum()),
            impact=(
                "Algunas fechas de reclamo son posteriores al snapshot. Usar "
                "last_complaint_date directamente como feature introduciría "
                "leakage temporal en un modelo de churn."
            ),
            fix=(
                "Usar solo reclamos ocurridos en o antes de reference_date, o "
                "derivar una variable segura como days_since_last_complaint_safe."
            ),
        )

    # ------------------------------------------------------------------
    # cancellation_reason como posible leakage post-evento
    # ------------------------------------------------------------------
    if {"cancellation_reason", "fla_churn90"}.issubset(df.columns):
        has_cancellation_reason = (
            df["cancellation_reason"].notna()
            & (df["cancellation_reason"].astype("string").str.strip() != "")
        )

        positives_with_reason = int(
            (has_cancellation_reason & df["fla_churn90"].eq(1)).sum()
        )
        negatives_with_reason = int(
            (has_cancellation_reason & df["fla_churn90"].eq(0)).sum()
        )

        if positives_with_reason > 0 and negatives_with_reason == 0:
            add_issue(
                column="cancellation_reason",
                rows_affected=positives_with_reason,
                impact=(
                    "cancellation_reason aparece únicamente en casos positivos "
                    "de churn. Aunque sería muy predictiva, probablemente "
                    "representa información posterior al evento y generaría "
                    "target leakage."
                ),
                fix=(
                    "Conservar la columna para auditoría y análisis descriptivo, "
                    "pero excluirla de features predictivas salvo que se confirme "
                    "que estaba disponible en el momento de predicción."
                ),
            )

    if {"cancellation_reason", "status"}.issubset(df.columns):
        has_cancellation_reason = (
            df["cancellation_reason"].notna()
            & (df["cancellation_reason"].astype("string").str.strip() != "")
        )

        approved_with_cancellation_reason = int(
            (has_cancellation_reason & df["status"].eq("approved")).sum()
        )

        add_issue(
            column="cancellation_reason",
            rows_affected=approved_with_cancellation_reason,
            impact=(
                "cancellation_reason aparece también en transacciones aprobadas. "
                "Esto sugiere que no representa el estado operativo de una "
                "transacción individual, sino información asociada al merchant "
                "o a un evento de cancelación/churn."
            ),
            fix=(
                "No usar cancellation_reason como señal transaccional. "
                "Mantenerla solo para auditoría o análisis descriptivo y "
                "excluirla de features predictivas salvo confirmación de "
                "disponibilidad temporal."
            ),
        )

    # ------------------------------------------------------------------
    # Dominios categóricos
    # ------------------------------------------------------------------
    if "status" in df.columns:
        expected_status = {"approved", "denied", "reversed"}
        unexpected_status = df["status"].notna() & ~df["status"].isin(expected_status)

        add_issue(
            column="status",
            rows_affected=int(unexpected_status.sum()),
            impact=(
                "Valores inesperados en status pueden romper definiciones de "
                "KPIs como TPV y approval_rate."
            ),
            fix=(
                "Normalizar status y confirmar con negocio o data owner el "
                "dominio válido de estados transaccionales."
            ),
        )

    if "channel" in df.columns:
        expected_channels = {"pos", "ecom", "pix", "tef"}
        unexpected_channels = df["channel"].notna() & ~df["channel"].isin(
            expected_channels
        )

        add_issue(
            column="channel",
            rows_affected=int(unexpected_channels.sum()),
            impact=(
                "Valores inesperados en channel pueden distorsionar métricas de "
                "mix de canal como pct_ecom."
            ),
            fix=(
                "Normalizar channel y confirmar con negocio o data owner el "
                "dominio válido de canales."
            ),
        )

    # ------------------------------------------------------------------
    # Desbalanceo del target
    # ------------------------------------------------------------------
    if "fla_churn90" in df.columns:
        target = df["fla_churn90"].dropna()

        if not target.empty:
            positive_rate = float(target.eq(1).mean())
            minority_rate = min(positive_rate, 1.0 - positive_rate)

            if minority_rate < 0.20:
                add_issue(
                    column="fla_churn90",
                    rows_affected=int(target.shape[0]),
                    impact=(
                        "El target de churn está desbalanceado. Accuracy puede "
                        "ser una métrica engañosa, porque un modelo podría "
                        "obtener buen resultado prediciendo mayoritariamente la "
                        "clase dominante."
                    ),
                    fix=(
                        "Usar métricas adecuadas para clasificación "
                        "desbalanceada, como ROC-AUC, PR-AUC / Average "
                        "Precision, recall@k y calibración."
                    ),
                )

    # ------------------------------------------------------------------
    # Summary enriquecido
    # ------------------------------------------------------------------
    summary: dict[str, Any] = {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "n_issues": int(len(issues)),
        "n_rows_raw": audit.get("n_rows_raw"),
        "n_rows_clean": audit.get("n_rows_clean"),
    }

    if "merchant_id" in df.columns:
        summary["n_merchants"] = int(df["merchant_id"].nunique(dropna=True))

    if "fla_churn90" in df.columns:
        target = df["fla_churn90"].dropna()

        if not target.empty:
            summary["target_positive_rate_rows"] = float(target.eq(1).mean())

        if {"merchant_id", "fla_churn90"}.issubset(df.columns):
            merchant_target = (
                df.dropna(subset=["merchant_id"])
                .groupby("merchant_id")["fla_churn90"]
                .first()
            )

            if not merchant_target.empty:
                summary["target_positive_rate_merchants"] = float(
                    merchant_target.eq(1).mean()
                )

                target_consistency = (
                    df.dropna(subset=["merchant_id"])
                    .groupby("merchant_id")["fla_churn90"]
                    .nunique()
                )
                summary["n_merchants_with_inconsistent_target"] = int(
                    (target_consistency > 1).sum()
                )

    if "amount" in df.columns:
        amount_non_null = df["amount"].dropna()

        if not amount_non_null.empty:
            summary["amount_p99"] = float(amount_non_null.quantile(0.99))
            summary["amount_max"] = float(amount_non_null.max())

    return {
        "issues": issues,
        "summary": summary,
    }


# -----------------------------------------------------------------------------
# 1.4  merchants_at_risk
# -----------------------------------------------------------------------------
def merchants_at_risk(df: pd.DataFrame, top_n: int = 200) -> pd.DataFrame:
    """
    Devuelve los `top_n` merchants con mayor "señal débil" de pre-churn.

    Tú decides la heurística. Justifícala en `DECISIONS.md`.

    Columnas mínimas esperadas:
      - merchant_id
      - risk_score          (float, mayor = más riesgo)
      - top_signal          (str, qué señal dominó tu score)

    Args:
        df: DataFrame limpio.
        top_n: número de merchants a devolver.

    Returns:
        DataFrame ordenado por risk_score descendente.
    """
    # TODO: implementa
    raise NotImplementedError("Parte 1.4 · merchants_at_risk")


# -----------------------------------------------------------------------------
# Entry point — genera artefactos en outputs/
# -----------------------------------------------------------------------------
def main(csv_path: str) -> None:
    """Carga, calcula KPIs y reporte, y persiste en outputs/."""
    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)

    df = load_clean(csv_path)

    kpis = monthly_kpis(df)
    kpis.to_csv(outputs / "monthly_kpis.csv", index=False)

    report = quality_report(df)
    (outputs / "quality_report.json").write_text(json.dumps(report, indent=2, default=str))

    at_risk = merchants_at_risk(df, top_n=200)
    at_risk.to_csv(outputs / "merchants_at_risk.csv", index=False)

    print("✓ Outputs generados en outputs/")


if __name__ == "__main__":
    csv = sys.argv[1] if len(sys.argv) > 1 else "data/transactions_sample.csv"
    main(csv)
