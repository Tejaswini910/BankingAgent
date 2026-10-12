"""Create the schema and seed a mock banking customer."""

from database.db import get_connection


def initialize_database() -> None:
    """Create tables if needed and add the demo customer once."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                salary REAL NOT NULL CHECK (salary >= 0),
                account_number TEXT NOT NULL UNIQUE,
                kyc_status TEXT NOT NULL CHECK (kyc_status IN ('VERIFIED', 'PENDING'))
            );

            CREATE TABLE IF NOT EXISTS loan_applications (
                application_id TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                loan_amount REAL NOT NULL CHECK (loan_amount > 0),
                tenure INTEGER NOT NULL CHECK (tenure > 0),
                emi REAL NOT NULL CHECK (emi > 0),
                status TEXT NOT NULL CHECK (status IN ('Submitted', 'Pending')),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            INSERT OR IGNORE INTO customers
                (id, name, salary, account_number, kyc_status)
            VALUES (1, 'Aarav Sharma', 60000, 'XXXXXX1234', 'VERIFIED');
            """
        )


if __name__ == "__main__":
    initialize_database()
    print("Database initialized with demo customer id 1.")
