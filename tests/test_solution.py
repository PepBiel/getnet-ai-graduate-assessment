"""
Tests para las Partes 1-3 (pandas, ML).

Añade aquí los tests que validan tu código. No hay tests obligatorios para
estas partes, pero **tener tests propios reales suma puntos** (bonus).

Recomendación mínima:
  - test_load_clean_returns_dataframe
  - test_monthly_kpis_columns
  - test_quality_report_finds_at_least_n_issues
  - test_merchants_at_risk_top_n_shape
"""
from __future__ import annotations

import pandas as pd
import pytest


# Ejemplo de fixture (adáptalo a tu implementación)
@pytest.fixture
def tiny_df() -> pd.DataFrame:
    """Mini DataFrame para tests rápidos sin depender del CSV completo."""
    return pd.DataFrame(
        {
            "transaction_id": [1, 2, 3, 4],
            "merchant_id": [10, 10, 11, 11],
            "transaction_date": pd.to_datetime(
                ["2025-01-15", "2025-01-20", "2025-02-01", "2025-02-03"]
            ),
            "amount": [100.0, 50.0, 200.0, 75.0],
            "status": ["approved", "denied", "approved", "approved"],
            "channel": ["pos", "ecom", "ecom", "pos"],
        }
    )


def test_smoke_pandas_imported(tiny_df: pd.DataFrame) -> None:
    """Smoke test mínimo para confirmar que pytest detecta el módulo."""
    assert len(tiny_df) == 4


def test_load_clean_parses_types_and_keeps_traceability(tmp_path) -> None:
    from src.parte1_pandas import load_clean

    raw = pd.DataFrame(
        {
            "transaction_id": [1, 2, 3],
            "merchant_id": [10, 10, 11],
            "transaction_date": ["2025-09-11", "12/09/2025", "2025-10-02"],
            "amount": ["1.234,56", "18,50", None],
            "status": [" APPROVED ", "Denied", "approved"],
            "channel": [" POS ", "ECom", "pix"],
            "cancellation_reason": [None, "high_fees", None],
            "reference_date": ["2025-09-30", "2025-09-30", "2025-09-30"],
            "fla_churn90": [0, 1, 0],
            "last_complaint_date": [None, "2025-10-01", None],
            "segment": ["SMB", "SMB", "Enterprise"],
            "mcc": [5411, 5411, 7995],
            "dat_process": ["2025-09-11", "2025-09-12", "2025-10-02"],
        }
    )
    path = tmp_path / "transactions.csv"
    raw.to_csv(path, index=False)

    out = load_clean(path)

    assert out.loc[out["transaction_id"] == 1, "amount"].item() == pytest.approx(1234.56)
    assert pd.api.types.is_datetime64_any_dtype(out["transaction_date"])
    assert pd.api.types.is_datetime64_any_dtype(out["reference_date"])
    assert pd.api.types.is_datetime64_any_dtype(out["last_complaint_date"])
    assert pd.api.types.is_datetime64_any_dtype(out["dat_process"])
    assert out.loc[out["transaction_id"] == 1, "status"].item() == "approved"
    assert out.loc[out["transaction_id"] == 2, "channel"].item() == "ecom"
    assert pd.api.types.is_string_dtype(out["mcc"])
    assert {"amount_raw", "transaction_date_raw", "reference_date_raw"}.issubset(out.columns)
    assert (out["transaction_date"] > out["reference_date"]).any()


def test_load_clean_deduplicates_by_business_columns(tmp_path) -> None:
    from src.parte1_pandas import load_clean

    raw = pd.DataFrame(
        {
            "transaction_id": [1, 2, 3],
            "merchant_id": [10, 10, 10],
            "transaction_date": ["2025-09-11", "2025-09-11", "2025-09-12"],
            "amount": ["18,50", "18,50", "20,00"],
            "status": ["approved", "approved", "approved"],
            "channel": ["pos", "pos", "pos"],
            "cancellation_reason": [None, None, None],
            "reference_date": ["2025-09-30", "2025-09-30", "2025-09-30"],
            "fla_churn90": [0, 0, 0],
            "last_complaint_date": [None, None, None],
            "segment": ["SMB", "SMB", "SMB"],
            "mcc": ["5411", "5411", "5411"],
            "dat_process": ["2025-09-11", "2025-09-11", "2025-09-12"],
        }
    )
    path = tmp_path / "transactions.csv"
    raw.to_csv(path, index=False)

    out = load_clean(path)

    assert len(out) == 2
    assert out.attrs["load_clean_audit"]["business_duplicate_rows_removed"] == 1


def test_load_clean_requires_core_columns(tmp_path) -> None:
    from src.parte1_pandas import load_clean

    path = tmp_path / "bad.csv"
    pd.DataFrame({"transaction_id": [1]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Missing required columns"):
        load_clean(path)


def test_monthly_kpis_computes_expected_metrics() -> None:
    from src.parte1_pandas import monthly_kpis

    df = pd.DataFrame(
        {
            "transaction_id": ["t1", "t2", "t3", "t4"],
            "merchant_id": [1, 1, 1, 1],
            "transaction_date": pd.to_datetime(
                ["2025-07-01", "2025-07-02", "2025-07-03", "2025-07-04"]
            ),
            "amount": [100.0, 50.0, 20.0, 30.0],
            "status": ["approved", "approved", "denied", "reversed"],
            "channel": ["ecom", "pos", "ecom", "pos"],
        }
    )

    result = monthly_kpis(df)

    assert result.columns.tolist() == [
        "merchant_id",
        "month",
        "tpv",
        "approval_rate",
        "pct_ecom",
        "n_tx",
    ]
    assert len(result) == 1

    row = result.iloc[0]
    assert row["merchant_id"] == 1
    assert row["month"] == pd.Timestamp("2025-07-01")
    assert row["tpv"] == 150.0
    assert row["n_tx"] == 4
    assert row["approval_rate"] == 0.5
    assert row["pct_ecom"] == pytest.approx(100.0 / 150.0)


def test_monthly_kpis_handles_zero_tpv() -> None:
    from src.parte1_pandas import monthly_kpis

    df = pd.DataFrame(
        {
            "transaction_id": ["t1", "t2"],
            "merchant_id": [1, 1],
            "transaction_date": pd.to_datetime(["2025-07-01", "2025-07-02"]),
            "amount": [100.0, 50.0],
            "status": ["denied", "reversed"],
            "channel": ["ecom", "pos"],
        }
    )

    result = monthly_kpis(df)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["merchant_id"] == 1
    assert row["month"] == pd.Timestamp("2025-07-01")
    assert row["tpv"] == 0.0
    assert row["approval_rate"] == 0.0
    assert row["pct_ecom"] == 0.0
    assert row["n_tx"] == 2


def test_monthly_kpis_groups_by_merchant_and_month() -> None:
    from src.parte1_pandas import monthly_kpis

    df = pd.DataFrame(
        {
            "transaction_id": ["t1", "t2", "t3"],
            "merchant_id": [1, 1, 2],
            "transaction_date": pd.to_datetime(
                ["2025-07-01", "2025-08-01", "2025-07-15"]
            ),
            "amount": [100.0, 200.0, 300.0],
            "status": ["approved", "approved", "approved"],
            "channel": ["pos", "ecom", "ecom"],
        }
    )

    result = monthly_kpis(df)

    expected_months = {
        (1, pd.Timestamp("2025-07-01")),
        (1, pd.Timestamp("2025-08-01")),
        (2, pd.Timestamp("2025-07-01")),
    }
    actual_months = set(zip(result["merchant_id"], result["month"]))

    assert len(result) == 3
    assert actual_months == expected_months


def test_monthly_kpis_raises_on_missing_required_columns() -> None:
    from src.parte1_pandas import monthly_kpis

    df = pd.DataFrame(
        {
            "merchant_id": [1],
            "transaction_date": pd.to_datetime(["2025-07-01"]),
            "amount": [100.0],
            "status": ["approved"],
        }
    )

    with pytest.raises(ValueError, match="Missing required columns"):
        monthly_kpis(df)


# TODO: añade tus tests reales. Ejemplos:
#
# def test_monthly_kpis_returns_one_row_per_merchant_month(tiny_df):
#     from src.parte1_pandas import monthly_kpis
#     out = monthly_kpis(tiny_df)
#     assert {"merchant_id", "month", "tpv", "approval_rate", "n_tx"}.issubset(out.columns)
#     assert len(out) == 2  # 2 merchants × 1 mes activo cada uno
