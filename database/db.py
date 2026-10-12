"""Reusable SQLite access helpers for the banking support agent."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


DATABASE_PATH = Path(__file__).resolve().parent / "banking.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a configured connection to the project database."""
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_customer(customer_id: int) -> dict[str, Any] | None:
    """Return a customer record, or ``None`` when it does not exist."""
    with get_connection() as connection:
        row = connection.execute(
            """SELECT id, name, salary, account_number, kyc_status
               FROM customers WHERE id = ?""",
            (customer_id,),
        ).fetchone()
    return dict(row) if row else None


def list_applications(customer_id: int | None = None) -> list[dict[str, Any]]:
    """List loan applications, optionally restricted to one customer."""
    with get_connection() as connection:
        if customer_id is None:
            rows = connection.execute(
                """SELECT application_id, customer_id, loan_amount, tenure, emi, status
                   FROM loan_applications ORDER BY rowid DESC"""
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT application_id, customer_id, loan_amount, tenure, emi, status
                   FROM loan_applications WHERE customer_id = ? ORDER BY rowid DESC""",
                (customer_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def create_application(
    customer_id: int,
    loan_amount: float,
    tenure_years: int,
    emi: float,
) -> dict[str, Any]:
    """Insert an application and return the persisted record."""
    application_id = f"LN-{uuid.uuid4().hex[:10].upper()}"
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO loan_applications
               (application_id, customer_id, loan_amount, tenure, emi, status)
               VALUES (?, ?, ?, ?, ?, 'Submitted')""",
            (application_id, customer_id, loan_amount, tenure_years, round(emi, 2)),
        )
        row = connection.execute(
            """SELECT application_id, customer_id, loan_amount, tenure, emi, status
               FROM loan_applications WHERE application_id = ?""",
            (application_id,),
        ).fetchone()
    return dict(row)
