# Smart Banking Support Agent

A runnable single-agent banking support demo built with Python, LangChain, FastAPI, SQLite, and an OpenAI-compatible Ollama endpoint. It looks up mock customer data, calculates a loan EMI, checks repayment eligibility, and only submits an application after explicit customer confirmation.

## Deploy with Streamlit Community Cloud

In Streamlit Community Cloud, select `banking-agent/streamlit_app.py` as the **Main file path** when the repository root is this workspace. If `banking-agent/` is itself the repository root, select `streamlit_app.py` instead. The project dependencies are in `banking-agent/requirements.txt`; commit and push the app, requirements, and `.streamlit/config.toml` before deploying. Streamlit Cloud starts the app and manages its port and public URL; do not use the Codespaces port URL or an Uvicorn command for this Streamlit app.

The Streamlit app has Overview, My applications, and Help & support pages. On Overview, **Check my eligibility** uses the local SQLite demo account and eligibility rules; an eligible customer with verified KYC can submit using the explicit-consent checkbox and button. The Help & support chat uses the LangChain agent and requires a reachable model provider. Use seeded demo customer ID `1`.

For Streamlit Community Cloud, open **App settings → Secrets** and add your reachable OpenAI-compatible model provider settings (replace the example values):

```toml
OLLAMA_BASE_URL = "https://your-provider.example/v1"
OLLAMA_MODEL = "your-tool-capable-model"
OLLAMA_API_KEY = "your-provider-api-key"
DEFAULT_INTEREST_RATE = "10.5"
```

Do not commit the API key. The local `.env` defaults point at local Ollama; `localhost` on Streamlit Cloud means the app's own server, not your computer. Choose a model/provider that supports tool calling. Chat messages are sent to that configured model provider, so use only this app's fictional demo customer data. Streamlit may reset the current conversation on refresh.

SQLite application records are local to the app instance and may not survive app restarts or redeployments.

### Run in GitHub Codespaces

From the workspace root, start the app with:

```bash
streamlit run banking-agent/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Open forwarded port `8501` in the **Ports** panel. A `502` from a `*.app.github.dev` URL means Codespaces cannot reach an app listening on that forwarded port; it is not the public Streamlit Cloud deployment URL. The Codespaces app must still be running, and may need to be restarted after a codespace stops or sleeps.

## Customer Application

- One LangChain tool-calling agent with four `@tool` functions.
uvicorn api.main:app --reload
- Eligibility rule: requested EMI plus existing monthly EMI must be no more than 50% of monthly salary.
- A consent guard that rejects tool submission unless the customer answered `yes` to a pending confirmation turn.
Open `http://127.0.0.1:8000/` for the customer-facing guided loan form. Enter customer ID `1` to use the seeded demo account. The form displays verified account status, EMI, eligibility, and the application decision step. It does not submit until the customer explicitly selects **Yes, submit application**.

The agent uses the configured 10.5% annual default when the customer does not provide a rate. For the seeded customer and example loan, the estimated EMI is approximately ₹16,251.22; including the existing ₹5,000 EMI, the total is below the customer's ₹30,000 limit.

The interactive API documentation is at `http://127.0.0.1:8000/docs`; this is for developers, not the customer application.

## Optional CLI

```bash
python app.py
```

The CLI supports the same scenario through a terminal conversation. It asks for customer ID when missing and requires a clear `yes` before submission.

## API Endpoints
- Seeded demo customer: ID `1`, monthly salary ₹60,000, verified KYC, masked account `XXXXXX1234`.
DEFAULT_INTEREST_RATE=10.5
- `POST /loan/workflow` (customer-form agent workflow)
```

For a fresh checkout, copy `.env.example` to `.env` before editing it.

`OLLAMA_BASE_URL` should be the OpenAI-compatible base URL (typically ending in `/v1`). `OLLAMA_API_KEY` can be a placeholder for local Ollama; use the credential required by your hosted compatible endpoint. The provided `.env` contains local defaults, not a real secret.

## Run the Agent

```bash
python app.py
```

Try the scenario:

```text
I want to apply for a personal loan of ₹5,00,000 for three years. My monthly salary is ₹60,000, and I already pay ₹5,000 as an EMI for another loan. Calculate my monthly EMI, check my loan eligibility, retrieve my account details, and help me submit a loan application if I qualify.
```

The agent asks for customer ID because a customer identity must not be guessed. Reply `1` for the seeded demo customer. If the request does not specify an interest rate, the agent uses the configured 10.5% annual default and tells you. When eligible with verified KYC, it asks exactly:

> You are eligible for the loan. Would you like me to submit the loan application? (yes/no)

Only a literal `yes` on that pending turn enables the submission tool. `no` ends the flow without inserting an application. The successful calculation at the defaults is approximately ₹16,251.22 monthly EMI; with the existing ₹5,000 EMI, the total is below the customer's ₹30,000 limit.

## Run the API

From this directory:

```bash
uvicorn api.main:app --reload
```

Interactive docs are available at `http://127.0.0.1:8000/docs`.

- `GET /customer/{id}`
- `POST /loan/apply`
- `GET /applications?customer_id=1` (omit the query to list all)

Example application request (the server computes EMI using `DEFAULT_INTEREST_RATE` and validates eligibility against SQLite):

```json
{
  "customer_id": 1,
  "loan_amount": 500000,
  "tenure_years": 3,
  "existing_emi": 5000,
  "consent": "yes"
}
```

The API submission route requires an explicit `consent: "yes"`, verified KYC, and a passing EMI burden check. It returns `422` when the burden is over the limit and `403` when KYC is not verified.

## Database

The database file `database/banking.db` is created on startup. `python -m database.init_db` initializes it manually. Initialization is idempotent and preserves existing application rows. The customer table contains `id`, `name`, `salary`, `account_number`, and `kyc_status`; applications contain `application_id`, `customer_id`, `loan_amount`, `tenure`, `emi`, and `status`.
