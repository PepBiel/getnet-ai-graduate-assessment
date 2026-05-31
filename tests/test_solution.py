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


def test_quality_report_returns_expected_structure() -> None:
    from src.parte1_pandas import quality_report

    df = pd.DataFrame(
        {
            "transaction_id": [1, 2, 3],
            "merchant_id": [10, 10, 20],
            "transaction_date": pd.to_datetime(
                ["2025-09-01", "2025-10-01", "2025-09-15"]
            ),
            "reference_date": pd.to_datetime(
                ["2025-09-30", "2025-09-30", "2025-09-30"]
            ),
            "amount": [100.0, None, 50.0],
            "status": ["approved", "denied", "reversed"],
            "channel": ["ecom", "pos", "pix"],
            "fla_churn90": [0, 0, 1],
            "last_complaint_date": pd.to_datetime([None, "2025-10-05", "2025-09-10"]),
            "cancellation_reason": [pd.NA, pd.NA, "price"],
        }
    )

    report = quality_report(df)

    assert set(report.keys()) == {"issues", "summary"}
    assert isinstance(report["issues"], list)
    assert isinstance(report["summary"], dict)
    assert report["summary"]["n_rows"] == 3
    assert report["summary"]["n_cols"] == len(df.columns)
    assert report["summary"]["n_issues"] == len(report["issues"])

    for issue in report["issues"]:
        assert set(issue.keys()) == {"column", "rows_affected", "impact", "fix"}
        assert isinstance(issue["rows_affected"], int)
        assert issue["rows_affected"] > 0
        assert issue["impact"]
        assert issue["fix"]


def test_quality_report_detects_key_issues() -> None:
    from src.parte1_pandas import quality_report

    df = pd.DataFrame(
        {
            "transaction_id": [1, 2, 3, 4, 5, 6],
            "merchant_id": [10, 10, 20, 20, 30, 30],
            "transaction_date": pd.to_datetime(
                [
                    "2025-09-01",
                    "2025-10-01",
                    "2025-09-15",
                    "2025-09-20",
                    "2025-09-21",
                    "2025-09-22",
                ]
            ),
            "reference_date": pd.to_datetime(
                [
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                ]
            ),
            "amount": [100.0, None, 50.0, 75.0, 25.0, 30.0],
            "status": ["approved", "denied", "approved", "approved", "approved", "denied"],
            "channel": ["ecom", "pos", "pix", "tef", "pos", "ecom"],
            "fla_churn90": [0, 0, 1, 0, 0, 0],
            "last_complaint_date": pd.to_datetime(
                [None, "2025-10-05", "2025-09-10", None, None, None]
            ),
            "cancellation_reason": [pd.NA, pd.NA, "price", pd.NA, pd.NA, pd.NA],
        }
    )

    report = quality_report(df)
    issue_columns = {issue["column"] for issue in report["issues"]}

    assert "amount" in issue_columns
    assert "transaction_date" in issue_columns
    assert "last_complaint_date" in issue_columns
    assert "cancellation_reason" in issue_columns
    assert "fla_churn90" in issue_columns


def test_quality_report_does_not_modify_dataframe() -> None:
    from src.parte1_pandas import quality_report

    df = pd.DataFrame(
        {
            "transaction_id": [1],
            "merchant_id": [10],
            "transaction_date": pd.to_datetime(["2025-10-01"]),
            "reference_date": pd.to_datetime(["2025-09-30"]),
            "amount": [None],
            "status": ["approved"],
            "channel": ["ecom"],
            "fla_churn90": [1],
            "last_complaint_date": pd.to_datetime(["2025-10-05"]),
            "cancellation_reason": ["price"],
        }
    )
    before = df.copy(deep=True)

    quality_report(df)

    pd.testing.assert_frame_equal(df, before)


def test_quality_report_detects_enriched_amount_and_cancellation_issues() -> None:
    from src.parte1_pandas import quality_report

    df = pd.DataFrame(
        {
            "transaction_id": [1, 2, 3, 4, 5, 6],
            "merchant_id": [10, 10, 20, 20, 30, 30],
            "transaction_date": pd.to_datetime(
                [
                    "2025-09-01",
                    "2025-09-02",
                    "2025-09-03",
                    "2025-09-04",
                    "2025-09-05",
                    "2025-09-06",
                ]
            ),
            "reference_date": pd.to_datetime(
                [
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                    "2025-09-30",
                ]
            ),
            "amount": [10.0, None, 10.0, 10.0, 10.0, 1000.0],
            "status": ["approved", "approved", "approved", "denied", "approved", "approved"],
            "channel": ["pos", "pos", "ecom", "pix", "tef", "ecom"],
            "fla_churn90": [0, 0, 1, 1, 0, 0],
            "last_complaint_date": pd.to_datetime([None, None, None, None, None, None]),
            "cancellation_reason": [pd.NA, pd.NA, "price", pd.NA, pd.NA, pd.NA],
        }
    )

    report = quality_report(df)

    amount_issues = [issue for issue in report["issues"] if issue["column"] == "amount"]
    cancellation_issues = [
        issue for issue in report["issues"] if issue["column"] == "cancellation_reason"
    ]

    assert any(
        issue["rows_affected"] == 1 and "transacciones aprobadas" in issue["impact"]
        for issue in amount_issues
    )
    assert any(
        issue["rows_affected"] == 1 and "asimétrica" in issue["impact"]
        for issue in amount_issues
    )
    assert any("únicamente en casos positivos" in issue["impact"] for issue in cancellation_issues)
    assert any("transacciones aprobadas" in issue["impact"] for issue in cancellation_issues)


def test_quality_report_summary_includes_context_metrics() -> None:
    from src.parte1_pandas import quality_report

    df = pd.DataFrame(
        {
            "transaction_id": [1, 2, 3, 4, 5],
            "merchant_id": [10, 10, 20, 20, 30],
            "transaction_date": pd.to_datetime(
                ["2025-09-01", "2025-09-02", "2025-09-03", "2025-09-04", "2025-09-05"]
            ),
            "reference_date": pd.to_datetime(
                ["2025-09-30", "2025-09-30", "2025-09-30", "2025-09-30", "2025-09-30"]
            ),
            "amount": [10.0, 20.0, 30.0, 40.0, 50.0],
            "status": ["approved", "denied", "approved", "denied", "approved"],
            "channel": ["pos", "ecom", "pix", "tef", "pos"],
            "fla_churn90": [0, 1, 0, 0, 1],
            "last_complaint_date": pd.to_datetime([None, None, None, None, None]),
            "cancellation_reason": [pd.NA, pd.NA, pd.NA, pd.NA, pd.NA],
        }
    )

    report = quality_report(df)
    summary = report["summary"]

    assert summary["n_merchants"] == 3
    assert summary["target_positive_rate_rows"] == pytest.approx(2 / 5)
    assert summary["target_positive_rate_merchants"] == pytest.approx(1 / 3)
    assert summary["n_merchants_with_inconsistent_target"] == 1
    assert summary["amount_p99"] == pytest.approx(49.6)
    assert summary["amount_max"] == 50.0


# TODO: añade tus tests reales. Ejemplos:
#
# def test_monthly_kpis_returns_one_row_per_merchant_month(tiny_df):
#     from src.parte1_pandas import monthly_kpis
#     out = monthly_kpis(tiny_df)
#     assert {"merchant_id", "month", "tpv", "approval_rate", "n_tx"}.issubset(out.columns)
#     assert len(out) == 2  # 2 merchants × 1 mes activo cada uno
