"""Streamlit entry point for the Smart Banking Support Agent demo."""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.banking_agent import BankingAssistant
from database.db import get_customer, list_applications
from database.init_db import initialize_database
from tools.application_tool import authorize_submission_for_turn, submit_loan_application
from tools.emi_tool import compute_monthly_emi
from tools.eligibility_tool import check_loan_eligibility


logger = logging.getLogger(__name__)
load_dotenv(PROJECT_ROOT / ".env")
DEFAULTS = {
    "customer_id": 1,
    "loan_amount": 500000.0,
    "tenure_years": 3,
    "existing_emi": 5000.0,
}

st.set_page_config(
    page_title="Smart Banking",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)
initialize_database()


def configured_secret(name: str) -> str:
    """Read a deployment secret first, then allow local environment/.env settings."""
    try:
        secret = st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        secret = None
    return str(secret or os.getenv(name, "")).strip()


DEFAULT_INTEREST_RATE = float(configured_secret("DEFAULT_INTEREST_RATE") or "10.5")
MODEL_CONFIG = {
    "model": configured_secret("OLLAMA_MODEL"),
    "base_url": configured_secret("OLLAMA_BASE_URL"),
    "api_key": configured_secret("OLLAMA_API_KEY"),
}
MODEL_CONFIGURED = all(MODEL_CONFIG.values())


def get_banking_assistant() -> BankingAssistant:
    """Create one LangChain agent for this Streamlit browser session."""
    assistant = st.session_state.get("banking_assistant")
    if assistant is None:
        if not MODEL_CONFIGURED:
            raise RuntimeError("Configure the model provider before starting the assistant.")
        assistant = BankingAssistant(
            model=MODEL_CONFIG["model"],
            base_url=MODEL_CONFIG["base_url"],
            api_key=MODEL_CONFIG["api_key"],
            default_rate=DEFAULT_INTEREST_RATE,
        )
        st.session_state["banking_assistant"] = assistant
    return assistant


def send_agent_message(message: str) -> None:
    """Send a user turn to LangChain and append only a successful response."""
    try:
        assistant = get_banking_assistant()
        response = assistant.respond(message)
    except Exception:
        logger.exception("LangChain banking assistant request failed")
        st.error(
            "The AI assistant could not complete that request. Check that the model "
            "endpoint is reachable, the model name is correct, and its API key is valid."
        )
        return

    messages: list[dict[str, str]] = st.session_state.setdefault("agent_messages", [])
    messages.extend(
        [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response},
        ]
    )


def render_agent_confirmation(assistant: BankingAssistant) -> None:
    """Require a separate affirmative confirmation before allowing submission."""
    if not assistant.awaiting_confirmation:
        return
    st.markdown("#### Submit an application")
    consent = st.checkbox(
        "I have reviewed this estimate and want to submit a demo application.",
        key="application_consent",
    )
    if st.button(
        "Submit application",
        type="primary",
        width="stretch",
        disabled=not consent,
        key="submit_application",
    ):
        send_agent_message("yes")
        st.session_state.pop("application_consent", None)
        st.rerun()
    if st.button("No, do not submit", key="decline_application"):
        send_agent_message("no")
        st.session_state.pop("application_consent", None)
        st.rerun()


for key, default in DEFAULTS.items():
    st.session_state.setdefault(key, default)

customer_id = int(st.session_state["customer_id"])
loan_amount = float(st.session_state["loan_amount"])
tenure_years = int(st.session_state["tenure_years"])
existing_emi = float(st.session_state["existing_emi"])
customer = get_customer(customer_id)
monthly_emi = (
    compute_monthly_emi(loan_amount, DEFAULT_INTEREST_RATE, tenure_years)
    if customer
    else None
)
current_inputs = (customer_id, loan_amount, tenure_years, existing_emi)
previous_inputs = st.session_state.get("eligibility_assessment_inputs")
if previous_inputs is not None and tuple(previous_inputs) != current_inputs:
    st.session_state.pop("banking_assistant", None)
    st.session_state["agent_messages"] = []
    st.session_state.pop("application_consent", None)
    st.session_state.pop("eligibility_assessment", None)
    st.session_state.pop("eligibility_assessment_inputs", None)
    st.session_state.pop("application_result", None)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { --green:#174a3e; --deep:#12372f; --ink:#182b25; --muted:#69766f; }
    .stApp { background:#f5f7f5; color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    .block-container { max-width:1180px; padding-top:2rem; padding-bottom:3rem; }
    h1,h2,h3 { font-family:'Manrope','DM Sans',sans-serif !important; color:var(--ink); }
    p,label,[data-testid="stMarkdownContainer"] { font-family:'DM Sans',sans-serif; }
    section[data-testid="stSidebar"] { background:#fff; border-right:1px solid #e6eae6; }
    .brand { display:flex; align-items:center; gap:10px; margin:5px 0 22px; color:#182b25; font:800 16px 'Manrope',sans-serif; }
    .brand-icon { display:grid; place-items:center; width:36px; height:36px; border-radius:9px; background:#12372f; color:#d8f078; font-size:12px; }
    .demo-tag { display:inline-block; margin:0 0 16px; padding:5px 8px; border:1px solid #e2e8de; border-radius:5px; background:#f5f8f2; color:#536b5c; font:700 10px 'DM Sans',sans-serif; letter-spacing:.06em; }
    .page-eyebrow { color:#648071; font:700 10px 'DM Sans',sans-serif; letter-spacing:.12em; text-transform:uppercase; }
    .page-heading { margin:5px 0 5px; color:#182b25; font:800 clamp(27px,3vw,36px) 'Manrope',sans-serif; letter-spacing:-.035em; }
    .page-description { margin-bottom:16px; color:#69766f; font:400 13px/1.6 'DM Sans',sans-serif; }
    .rate-note { display:inline-block; margin-bottom:12px; padding:7px 10px; border-radius:6px; background:#e9f0e7; color:#365f4c; font:700 11px 'DM Sans',sans-serif; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-color:#e2e8e2; border-radius:10px; background:#fff; }
    div.stButton > button[kind="primary"] { min-height:42px; border-radius:7px; background:#174a3e; border-color:#174a3e; font-weight:700; }
    div.stButton > button[kind="primary"]:hover { background:#226250; border-color:#226250; }
    div[data-testid="stMetric"] { padding:12px 13px; border:1px solid #e6ebe5; border-radius:8px; background:#fbfcfb; }
    div[data-testid="stMetricLabel"] { color:#69766f; }
    div[data-testid="stMetricValue"] { color:#174a3e; font-family:'Manrope',sans-serif; }
    .emi-panel { padding:16px; border:1px solid #dfe8dd; border-radius:8px; background:#f7f9f6; }
    .emi-label { color:#64736a; font:500 11px 'DM Sans',sans-serif; }
    .emi-amount { margin:4px 0 1px; color:#174a3e; font:800 30px 'Manrope',sans-serif; }
    .emi-footnote,.disclaimer { color:#7a867e; font:400 10px/1.6 'DM Sans',sans-serif; }
    @media (max-width:700px) { .block-container { padding-left:1rem; padding-right:1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        '<div class="brand"><span class="brand-icon">SB</span> Smart Banking</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="demo-tag">INTERACTIVE DEMO</div>', unsafe_allow_html=True)
    page = st.radio(
        "Workspace",
        ["Overview", "My applications", "Help & support"],
        label_visibility="collapsed",
        key="active_page",
    )
    st.divider()
    st.caption("DEMO PROFILE")
    if customer:
        st.markdown(f"**{customer['name']}**")
        st.caption(f"Customer ID {customer_id} · Account ending {customer['account_number'][-4:]}")
        st.caption(f"KYC: {customer['kyc_status'].title()}")
    else:
        st.warning("Demo customer record not found.")
    st.divider()
    if MODEL_CONFIGURED:
        st.caption(f"AI model: {MODEL_CONFIG['model']}")
    else:
        st.warning(
            "The Help & support AI chat is not configured. Eligibility checks and "
            "demo submissions do not require an AI model."
        )
    st.caption("Only use the fictional demo account; chat messages go to the configured AI provider.")
    if st.button("Start a new conversation", width="stretch"):
        for key in (
            "banking_assistant",
            "agent_messages",
            "agent_assessment_inputs",
            "application_consent",
        ):
            st.session_state.pop(key, None)
        st.rerun()
    st.caption("Mock data only. No real banking services are connected.")

if page == "Overview":
    st.markdown('<div class="page-eyebrow">Personal lending</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-heading">Loan overview</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-description">Explore an illustrative repayment estimate, '
        "then check it against the demo account’s affordability guideline.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="rate-note">Indicative annual interest rate &nbsp; '
        f'{DEFAULT_INTEREST_RATE:g}%</div>',
        unsafe_allow_html=True,
    )

    inputs_column, estimate_column = st.columns([1.15, 0.85], gap="large")
    with inputs_column:
        with st.container(border=True):
            st.subheader("Your loan details")
            st.caption("Change the details below to update your estimate.")
            customer_id = st.number_input(
                "Customer ID",
                min_value=1,
                step=1,
                key="customer_id",
                help="Use demo customer ID 1.",
            )
            loan_amount = st.number_input(
                "Loan amount (₹)",
                min_value=50000.0,
                max_value=5000000.0,
                step=25000.0,
                format="%.0f",
                key="loan_amount",
            )
            tenure_years = st.slider(
                "Repayment period",
                min_value=1,
                max_value=30,
                format="%d years",
                key="tenure_years",
            )
            existing_emi = st.number_input(
                "Existing monthly loan payments (₹)",
                min_value=0.0,
                max_value=1000000.0,
                step=500.0,
                format="%.0f",
                key="existing_emi",
                help="Include EMIs you currently pay on other loans.",
            )
            customer = get_customer(int(customer_id))
            if customer is None:
                monthly_emi = None
                st.error("Customer not found. Use demo customer ID 1.")
            else:
                monthly_emi = compute_monthly_emi(
                    float(loan_amount), DEFAULT_INTEREST_RATE, int(tenure_years)
                )
            if st.button(
                "Check my eligibility",
                type="primary",
                width="stretch",
                disabled=customer is None,
                key="check_eligibility",
            ):
                if customer is None:
                    st.error("Customer not found. Use demo customer ID 1.")
                else:
                    try:
                        assessment = json.loads(
                            check_loan_eligibility.invoke(
                                {
                                    "customer_id": int(customer_id),
                                    "loan_amount": float(loan_amount),
                                    "interest_rate": DEFAULT_INTEREST_RATE,
                                    "tenure_years": int(tenure_years),
                                    "existing_emi": float(existing_emi),
                                }
                            )
                        )
                        if "error" in assessment:
                            st.error(assessment["error"])
                        else:
                            assessment["account_verified"] = (
                                customer["kyc_status"] == "VERIFIED"
                            )
                            st.session_state["eligibility_assessment"] = assessment
                            st.session_state["eligibility_assessment_inputs"] = current_inputs
                            st.session_state.pop("application_result", None)
                    except Exception:
                        logger.exception("Banking eligibility assessment failed")
                        st.error("Eligibility could not be checked. Please try again.")

    with estimate_column:
        with st.container(border=True):
            st.subheader("Repayment estimate")
            if customer and monthly_emi is not None:
                total = monthly_emi + float(existing_emi)
                limit = float(customer["salary"]) * 0.5
                st.markdown(
                    f'<div class="emi-panel"><div class="emi-label">Estimated monthly EMI</div>'
                    f'<div class="emi-amount">₹{monthly_emi:,.0f}</div>'
                    f'<div class="emi-footnote">{tenure_years} years · '
                    f'{DEFAULT_INTEREST_RATE:g}% annual interest</div></div>',
                    unsafe_allow_html=True,
                )
                st.write("")
                first_metric, second_metric = st.columns(2)
                first_metric.metric("Existing EMIs", f"₹{existing_emi:,.0f}")
                second_metric.metric("Total per month", f"₹{total:,.0f}")
                st.progress(
                    min(total / limit, 1.0) if limit else 1.0,
                    text="Share of demo monthly income",
                )
                st.caption(f"Demo repayment guideline: up to ₹{limit:,.0f} per month.")
            else:
                st.info("Enter demo customer ID 1 to see your estimate.")

    assessment = st.session_state.get("eligibility_assessment")
    if customer and assessment and tuple(
        st.session_state.get("eligibility_assessment_inputs", ())
    ) == current_inputs:
        st.write("")
        with st.container(border=True):
            st.subheader("Eligibility assessment")
            st.caption(f"Assessment for {customer['name']} · customer ID {customer_id}")
            metric_one, metric_two, metric_three = st.columns(3)
            metric_one.metric(
                "Estimated new EMI",
                f"₹{assessment['requested_emi']:,.0f}",
            )
            metric_two.metric(
                "All monthly EMIs",
                f"₹{assessment['total_emi_burden']:,.0f}",
            )
            metric_three.metric(
                "Monthly guideline",
                f"₹{assessment['maximum_allowed_burden']:,.0f}",
            )
            if assessment["eligible"]:
                st.success("Within the demo affordability guideline.")
            else:
                st.warning(
                    "Above the demo affordability guideline. Try a smaller amount "
                    "or a longer repayment period."
                )
            if assessment["account_verified"]:
                st.caption("Demo KYC status: verified")
            else:
                st.warning("KYC must be verified before submitting an application.")

            if assessment["eligible"] and assessment["account_verified"]:
                application_result = st.session_state.get("application_result")
                if application_result:
                    st.success(
                        "Application submitted · Reference "
                        f"**{application_result['application_id']}**"
                    )
                else:
                    consent = st.checkbox(
                        "I have reviewed this estimate and want to submit a demo application.",
                        key="application_consent",
                    )
                    if st.button(
                        "Submit application",
                        type="primary",
                        width="stretch",
                        disabled=not consent,
                        key="submit_application",
                    ):
                        try:
                            with authorize_submission_for_turn():
                                result = json.loads(
                                    submit_loan_application.invoke(
                                        {
                                            "customer_id": int(customer_id),
                                            "loan_amount": float(loan_amount),
                                            "interest_rate": DEFAULT_INTEREST_RATE,
                                            "tenure_years": int(tenure_years),
                                            "existing_emi": float(existing_emi),
                                            "consent": "yes",
                                        }
                                    )
                                )
                            if "error" in result:
                                st.error(result["error"])
                            else:
                                st.session_state["application_result"] = result
                                st.rerun()
                        except Exception:
                            logger.exception("Banking loan application submission failed")
                            st.error(
                                "The application could not be submitted. Please try again."
                            )

    agent_messages: list[dict[str, str]] = st.session_state.get("agent_messages", [])
    if agent_messages:
        st.write("")
        with st.container(border=True):
            st.subheader("Conversation with the banking agent")
            for message in agent_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

elif page == "My applications":
    st.markdown('<div class="page-eyebrow">Your activity</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-heading">My applications</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-description">Review the sample applications created in this demo.</div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        applications = list_applications(customer_id)
        if applications:
            st.dataframe(applications, hide_index=True, width="stretch")
        else:
            st.info("No applications yet. Your submitted demo applications will appear here.")
            if st.button("Explore a loan estimate", type="primary"):
                st.session_state["active_page"] = "Overview"
                st.rerun()
    st.caption("Demo application history is stored locally and may reset when the app restarts.")

else:
    st.markdown('<div class="page-eyebrow">We’re here to help</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-heading">Help & support</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-description">Ask about your estimate, the demo eligibility '
        "guideline, or what happens when you submit.</div>",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown("**Chat with the LangChain banking agent**")
        st.caption(
            "The agent can call the demo account, EMI, eligibility, and application "
            "tools. It only submits after explicit confirmation."
        )
        agent_messages: list[dict[str, str]] = st.session_state.get("agent_messages", [])
        for message in agent_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        if not agent_messages:
            st.info(
                "For a guided assessment, first fill in the loan details on Overview. "
                "Or ask the agent a question below."
            )
        if MODEL_CONFIGURED:
            question = st.chat_input("Ask the banking agent…")
            if question:
                send_agent_message(question)
                st.rerun()
        else:
            st.warning(
                "Configure OLLAMA_MODEL, OLLAMA_BASE_URL, and OLLAMA_API_KEY in "
                "Streamlit Cloud Secrets to enable the LangChain agent."
            )
        current_assistant: BankingAssistant | None = st.session_state.get(
            "banking_assistant"
        )
        if current_assistant:
            render_agent_confirmation(current_assistant)
    with st.expander("How is the EMI estimated?"):
        st.write(
            "The estimate uses the loan amount, repayment term, and illustrative "
            f"{DEFAULT_INTEREST_RATE:g}% annual interest rate. A real lender's final "
            "offer may differ."
        )
    with st.expander("How is eligibility checked?"):
        st.write(
            "The new estimated EMI plus existing monthly EMIs is compared with "
            "50% of the monthly salary recorded for this fictional customer."
        )
    with st.expander("Is this a real loan offer?"):
        st.write(
            "No. This app uses fictional data, does not connect to a bank, and does "
            "not provide financial advice or a credit decision."
        )

st.markdown(
    '<p class="disclaimer" style="text-align:center;margin-top:24px">'
    "Smart Banking interactive demo · Fictional customer data · No real banking "
    "services connected</p>",
    unsafe_allow_html=True,
)
