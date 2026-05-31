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
    # TODO: implementa
    raise NotImplementedError("Parte 1.3 · quality_report")


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
