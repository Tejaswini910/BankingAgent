"""Single LangChain tool-calling agent and consent-aware chat manager."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tools.account_tool import get_account_details
from tools.application_tool import authorize_submission_for_turn, submit_loan_application
from tools.eligibility_tool import check_loan_eligibility
from tools.emi_tool import calculate_emi


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = """You are the single Smart Banking Support Agent. Work only with the supplied tools and their results; never invent account facts, eligibility, or application IDs.

Workflow:
1. Ask one concise follow-up question for required missing information. Never guess a customer ID. Required information includes customer ID, loan amount, tenure in years, and existing monthly EMI.
2. Retrieve the account with get_account_details, calculate EMI with calculate_emi, then call check_loan_eligibility with the customer ID, principal, rate, tenure, and existing EMI. The eligibility tool independently recalculates EMI and reads salary from SQLite.
3. If no interest rate was supplied, use the configured default annual rate of {default_rate}% and clearly state that assumption. Do not ask the customer to choose the bank's rate.
4. Only when the eligibility tool says eligible AND account KYC is VERIFIED, ask exactly: "You are eligible for the loan. Would you like me to submit the loan application? (yes/no)" Do not call submit_loan_application in that turn.
5. Submit only after the latest customer message explicitly says yes. Pass consent="yes" and the exact principal, rate, tenure, and existing EMI used for the successful eligibility check. A no means stop without submission. Never treat ambiguous language as consent.
6. If not eligible or KYC is not verified, do not ask for application consent and do not submit.
7. After the workflow is complete, provide a concise explanation and this exact summary format. Use N/A for an application ID when none was created; Application Status is Submitted or Pending.

Loan Summary
-------------
Loan Amount: ₹<amount>
Tenure: <years> Years
Monthly EMI: ₹<monthly EMI>
Eligibility Status: <Eligible/Not Eligible>
Account Status: <Verified/Not Verified>
Application Status: <Submitted/Pending>
Application ID: <ID or N/A>
"""


class BankingAssistant:
    """Manage chat history and enforce explicit consent around one agent."""

    def __init__(self) -> None:
        load_dotenv(PROJECT_ROOT / ".env")
        default_rate = os.getenv("DEFAULT_INTEREST_RATE", "10.5")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("OLLAMA_API_KEY", "ollama")

        llm = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0,
        )
        tools = [
            calculate_emi,
            check_loan_eligibility,
            get_account_details,
            submit_loan_application,
        ]
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT.format(default_rate=default_rate)),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(llm, tools, prompt)
        self.executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=8,
            return_intermediate_steps=True,
        )
        self.chat_history: list[HumanMessage | AIMessage] = []
        self.awaiting_confirmation = False
        self.eligible: bool | None = None
        self.account_verified: bool | None = None
        self.customer_details: dict[str, Any] | None = None
        self.total_emi_burden: float | None = None
        self.maximum_allowed_burden: float | None = None
        self.loan_amount: float | None = None
        self.tenure_years: int | None = None
        self.interest_rate: float | None = None
        self.monthly_emi: float | None = None
        self.application_id: str | None = None

    @staticmethod
    def _read_json(value: Any) -> dict[str, Any] | None:
        """Parse JSON tool output when possible."""
        if not isinstance(value, str):
            return None
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _capture_tool_results(self, steps: list[tuple[Any, Any]]) -> None:
        """Keep the authoritative calculation and account outcomes for consent."""
        for action, observation in steps:
            data = self._read_json(observation)
            if data is None:
                continue
            if action.tool == "get_account_details" and "error" not in data:
                self.account_verified = data.get("kyc_status") == "VERIFIED"
                self.customer_details = data
            elif action.tool == "calculate_emi" and "monthly_emi" in data:
                self.monthly_emi = float(data["monthly_emi"])
                self.loan_amount = float(data["loan_amount"])
                self.tenure_years = int(data["tenure_years"])
                self.interest_rate = float(data["interest_rate"])
            elif action.tool == "check_loan_eligibility" and "eligible" in data:
                self.eligible = bool(data["eligible"])
                self.total_emi_burden = float(data["total_emi_burden"])
                self.maximum_allowed_burden = float(data["maximum_allowed_burden"])
            elif action.tool == "submit_loan_application" and "application_id" in data:
                self.application_id = str(data["application_id"])
                self.loan_amount = float(data["loan_amount"])
                self.tenure_years = int(data["tenure"])
                self.monthly_emi = float(data["emi"])

    def _summary(self, application_status: str, application_id: str) -> str:
        """Render the requested stable summary from known tool results."""
        amount = f"{self.loan_amount:g}" if self.loan_amount is not None else "N/A"
        tenure = str(self.tenure_years) if self.tenure_years is not None else "N/A"
        emi = f"{self.monthly_emi:.2f}" if self.monthly_emi is not None else "N/A"
        eligibility = "Eligible" if self.eligible is True else "Not Eligible"
        account_status = "Verified" if self.account_verified is True else "Not Verified"
        return (
            "Loan Summary\n"
            "-------------\n"
            f"Loan Amount: ₹{amount}\n"
            f"Tenure: {tenure} Years\n"
            f"Monthly EMI: ₹{emi}\n"
            f"Eligibility Status: {eligibility}\n"
            f"Account Status: {account_status}\n"
            f"Application Status: {application_status}\n"
            f"Application ID: {application_id}"
        )

    def _invoke(self, user_text: str, allow_submission: bool = False) -> str:
        """Run the single agent and update state from its actual tool results."""
        if allow_submission:
            with authorize_submission_for_turn():
                result = self.executor.invoke(
                    {"input": user_text, "chat_history": self.chat_history}
                )
        else:
            result = self.executor.invoke(
                {"input": user_text, "chat_history": self.chat_history}
            )

        response = str(result["output"])
        steps = result.get("intermediate_steps", [])
        self._capture_tool_results(steps)
        self.chat_history.extend(
            [HumanMessage(content=user_text), AIMessage(content=response)]
        )

        if self.application_id:
            self.awaiting_confirmation = False
            return self._summary("Submitted", self.application_id)

        if re.search(r"would you like me to submit the loan application\?", response, re.I):
            self.awaiting_confirmation = self.eligible is True and self.account_verified is True
            if not self.awaiting_confirmation:
                return (
                    "I can’t request application confirmation until eligibility and verified KYC "
                    "have both been established. Please provide any missing details."
                )

        if self.eligible is False or self.account_verified is False:
            self.awaiting_confirmation = False
        return response

    def respond(self, user_text: str) -> str:
        """Handle a customer turn, gating application submission on a clear yes."""
        answer = user_text.strip().casefold()
        if self.awaiting_confirmation:
            if answer == "no":
                self.awaiting_confirmation = False
                response = self._summary("Pending", "N/A")
                self.chat_history.extend(
                    [HumanMessage(content=user_text), AIMessage(content=response)]
                )
                return response
            if answer == "yes":
                self.awaiting_confirmation = False
                return self._invoke(user_text, allow_submission=True)

            self.awaiting_confirmation = False
            self.eligible = None
            self.account_verified = None
            self.loan_amount = None
            self.tenure_years = None
            self.interest_rate = None
            self.monthly_emi = None
            return self._invoke(
                "The previous confirmation is no longer valid. Re-evaluate this request "
                f"without submitting an application: {user_text}"
            )

        self.eligible = None
        self.account_verified = None
        self.loan_amount = None
        self.tenure_years = None
        self.interest_rate = None
        self.monthly_emi = None
        self.application_id = None
        return self._invoke(user_text)
