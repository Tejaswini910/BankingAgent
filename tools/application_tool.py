"""Consent-gated LangChain tool for persisting loan applications."""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from langchain_core.tools import tool

from database.db import create_application, get_customer
from tools.emi_tool import compute_monthly_emi


_submission_authorized: ContextVar[bool] = ContextVar("submission_authorized", default=False)


@contextmanager
def authorize_submission_for_turn() -> Iterator[None]:
    """Permit submission only during a turn with explicit customer consent."""
    token = _submission_authorized.set(True)
    try:
        yield
    finally:
        _submission_authorized.reset(token)


@tool
def submit_loan_application(
    customer_id: int,
    loan_amount: float,
    interest_rate: float,
    tenure_years: int,
    existing_emi: float,
    consent: str,
) -> str:
    """Submit a loan application after explicit customer consent and validation."""
    if not _submission_authorized.get() or consent.strip().casefold() != "yes":
        return json.dumps({"error": "Explicit customer confirmation is required before submission."})

    customer = get_customer(customer_id)
    if customer is None:
        return json.dumps({"error": f"Customer {customer_id} was not found."})
    if customer["kyc_status"] != "VERIFIED":
        return json.dumps({"error": "Application cannot be submitted because KYC is not verified."})
    if existing_emi < 0:
        return json.dumps({"error": "Existing EMI cannot be negative."})
    try:
        emi = compute_monthly_emi(loan_amount, interest_rate, tenure_years)
    except ValueError as error:
        return json.dumps({"error": str(error)})
    if emi + existing_emi > float(customer["salary"]) * 0.5:
        return json.dumps({"error": "Application cannot be submitted: EMI burden exceeds 50% of salary."})

    application = create_application(customer_id, loan_amount, tenure_years, emi)
    return json.dumps(application)
