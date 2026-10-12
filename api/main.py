"""FastAPI endpoints for mock customer and loan application data."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import Lock
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent.banking_agent import BankingAssistant
from database.db import create_application, get_customer, list_applications
from database.init_db import initialize_database
from tools.emi_tool import compute_monthly_emi


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DEFAULT_INTEREST_RATE = float(os.getenv("DEFAULT_INTEREST_RATE", "10.5"))


class LoanApplicationRequest(BaseModel):
    """Validated payload for a directly confirmed loan application."""

    customer_id: int = Field(gt=0)
    loan_amount: float = Field(gt=0)
    tenure_years: int = Field(gt=0)
    existing_emi: float = Field(ge=0)
    consent: Literal["yes"]


class LoanWorkflowRequest(BaseModel):
    """Guided loan assessment or explicit submit/decline decision."""

    session_id: str = Field(pattern=r"^[a-fA-F0-9-]{36}$")
    decision: Literal["assess", "yes", "no"]
    customer_id: int = Field(gt=0)
    loan_amount: float = Field(gt=0)
    tenure_years: int = Field(gt=0)
    existing_emi: float = Field(ge=0)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize the local SQLite schema before serving requests."""
    initialize_database()
    yield


app = FastAPI(title="Smart Banking Support Agent API", version="1.0.0", lifespan=lifespan)
_agent_sessions: dict[str, BankingAssistant] = {}
_session_locks: dict[str, Lock] = {}
_sessions_guard = Lock()


@app.get("/", include_in_schema=False)
def customer_application_page() -> FileResponse:
    """Serve the customer-facing guided loan application page."""
    page_path = Path(__file__).resolve().parents[1] / "web" / "index.html"
    return FileResponse(page_path, media_type="text/html")


@app.post("/loan/workflow")
def loan_workflow(request: LoanWorkflowRequest) -> dict:
    """Coordinate assessment and consent through one agent per browser session."""
    with _sessions_guard:
        if request.decision == "assess":
            assistant = BankingAssistant()
            _agent_sessions[request.session_id] = assistant
            _session_locks[request.session_id] = Lock()
        else:
            assistant = _agent_sessions.get(request.session_id)
            if assistant is None:
                raise HTTPException(status_code=409, detail="Start a new eligibility check first")
        session_lock = _session_locks[request.session_id]

    if request.decision == "assess":
        customer_message = (
            f"My customer ID is {request.customer_id}. I want a personal loan of "
            f"INR {request.loan_amount:g} for {request.tenure_years} years. My existing "
            f"monthly EMI is INR {request.existing_emi:g}. Retrieve my account details, "
            "calculate the EMI using the configured bank interest rate, and check my eligibility. "
            "Do not submit an application before asking for my explicit confirmation."
        )
    else:
        customer_message = request.decision

    with session_lock:
        try:
            reply = assistant.respond(customer_message)
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail="The banking assistant could not reach its configured AI service. Please try again later.",
            ) from error

    customer = assistant.customer_details or {}
    return {
        "reply": reply,
        "awaiting_confirmation": assistant.awaiting_confirmation,
        "facts": {
            "customer_name": customer.get("name"),
            "account_number": customer.get("account_number"),
            "salary": assistant.customer_details.get("salary") if assistant.customer_details else None,
            "account_verified": assistant.account_verified,
            "loan_amount": assistant.loan_amount,
            "tenure_years": assistant.tenure_years,
            "interest_rate": assistant.interest_rate,
            "monthly_emi": assistant.monthly_emi,
            "total_emi_burden": assistant.total_emi_burden,
            "maximum_allowed_burden": assistant.maximum_allowed_burden,
            "eligible": assistant.eligible,
            "application_id": assistant.application_id,
        },
    }


@app.get("/customer/{id}")
def read_customer(id: int) -> dict:
    """Return the customer's account details."""
    customer = get_customer(id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.post("/loan/apply", status_code=201)
def apply_for_loan(application: LoanApplicationRequest) -> dict:
    """Submit an application after explicit consent and server-side checks."""
    customer = get_customer(application.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer["kyc_status"] != "VERIFIED":
        raise HTTPException(status_code=403, detail="KYC must be verified before applying")
    emi = compute_monthly_emi(
        application.loan_amount,
        DEFAULT_INTEREST_RATE,
        application.tenure_years,
    )
    if emi + application.existing_emi > float(customer["salary"]) * 0.5:
        raise HTTPException(status_code=422, detail="Total EMI burden exceeds 50% of monthly salary")

    result = create_application(
        application.customer_id,
        application.loan_amount,
        application.tenure_years,
        emi,
    )
    result["interest_rate"] = DEFAULT_INTEREST_RATE
    return result


@app.get("/applications")
def read_applications(customer_id: int | None = Query(default=None, gt=0)) -> list[dict]:
    """List loan applications, optionally filtered by customer ID."""
    return list_applications(customer_id)
