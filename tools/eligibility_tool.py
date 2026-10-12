"""LangChain tool for checking monthly repayment capacity."""

import json

from langchain_core.tools import tool

from database.db import get_customer
from tools.emi_tool import compute_monthly_emi


@tool
def check_loan_eligibility(
    customer_id: int,
    loan_amount: float,
    interest_rate: float,
    tenure_years: int,
    existing_emi: float,
) -> str:
    """Check if requested plus existing EMIs are at most 50% of salary."""
    if existing_emi < 0:
        return json.dumps({"error": "EMI values cannot be negative."})

    customer = get_customer(customer_id)
    if customer is None:
        return json.dumps({"error": f"Customer {customer_id} was not found."})

    try:
        monthly_emi = compute_monthly_emi(loan_amount, interest_rate, tenure_years)
    except ValueError as error:
        return json.dumps({"error": str(error)})

    salary = float(customer["salary"])
    total_emi = monthly_emi + existing_emi
    limit = salary * 0.5
    return json.dumps(
        {
            "customer_id": customer_id,
            "monthly_salary": salary,
            "requested_emi": round(monthly_emi, 2),
            "interest_rate": interest_rate,
            "existing_emi": round(existing_emi, 2),
            "total_emi_burden": round(total_emi, 2),
            "maximum_allowed_burden": round(limit, 2),
            "eligible": total_emi <= limit,
        }
    )
