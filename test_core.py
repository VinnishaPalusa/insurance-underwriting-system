import pytest
from src.core import calculate_premium, evaluate_underwriting


def test_premium_is_reproducible():
    assert calculate_premium(1_000_000, 0.01, 1.2) == 12_000.00
    assert calculate_premium(1_000_000, 0.01, 1.2) == calculate_premium(1_000_000, 0.01, 1.2)


def test_premium_rejects_nonpositive_inputs():
    with pytest.raises(ValueError):
        calculate_premium(0, 0.01, 1.0)


def test_high_risk_is_referred():
    outcome, reasons, score = evaluate_underwriting(30, 3, 500_000, 100_000, 5_000_000, 18, 10, "HIGH")
    assert outcome == "REFERRED"
    assert reasons
    assert score > 0


def test_underage_applicant_is_declined():
    outcome, reasons, _ = evaluate_underwriting(17, 2, 500_000, 100_000, 5_000_000, 18, 10, "LOW")
    assert outcome == "DECLINED"
    assert any("age" in reason.lower() for reason in reasons)


def test_missing_risk_is_referred():
    outcome, reasons, _ = evaluate_underwriting(30, 2, 500_000, 100_000, 5_000_000, 18, 10, None)
    assert outcome == "REFERRED"
    assert "missing" in reasons[0].lower()
