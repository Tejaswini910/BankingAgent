"""LangChain tool for standard fixed-rate monthly EMI calculations."""

import json

from langchain_core.tools import tool


def compute_monthly_emi(loan_amount: float, interest_rate: float, tenure_years: int) -> float:
    """Return the standard fixed-rate monthly EMI for a loan."""
    if loan_amount <= 0 or interest_rate < 0 or tenure_years <= 0:
        raise ValueError("Loan amount and tenure must be positive; rate cannot be negative.")

    months = tenure_years * 12
    monthly_rate = interest_rate / (12 * 100)
    if monthly_rate == 0:
        return loan_amount / months
    rate_factor = (1 + monthly_rate) ** months
    return loan_amount * monthly_rate * rate_factor / (rate_factor - 1)


@tool
def calculate_emi(loan_amount: float, interest_rate: float, tenure_years: int) -> str:
    """Calculate monthly EMI from principal, annual interest percent, and years."""
    try:
        monthly_emi = compute_monthly_emi(loan_amount, interest_rate, tenure_years)
    except ValueError as error:
        return json.dumps({"error": str(error)})
    return json.dumps(
        {
            "loan_amount": loan_amount,
            "interest_rate": interest_rate,
            "tenure_years": tenure_years,
            "monthly_emi": round(monthly_emi, 2),
            "currency": "INR",
        }
    )
