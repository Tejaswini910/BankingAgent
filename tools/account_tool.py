"""LangChain tool for retrieving a customer's mock account information."""

import json

from langchain_core.tools import tool

from database.db import get_customer


@tool
def get_account_details(customer_id: int) -> str:
    """Fetch a customer's name, salary, masked account number, and KYC status."""
    customer = get_customer(customer_id)
    if customer is None:
        return json.dumps({"error": f"Customer {customer_id} was not found."})
    return json.dumps(customer)
