"""Interactive command-line entry point for Smart Banking Support Agent."""

from database.init_db import initialize_database
from agent.banking_agent import BankingAssistant


def main() -> None:
    """Initialize local data and start a conversational agent session."""
    initialize_database()
    assistant = BankingAssistant()
    print("Smart Banking Support Agent")
    print("Demo customer: id 1 (Aarav Sharma). Type 'exit' to quit.")
    while True:
        try:
            customer_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if customer_message.casefold() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not customer_message:
            continue
        try:
            print(f"Agent: {assistant.respond(customer_message)}")
        except Exception as error:
            print(f"Agent error: {error}")
            print("Check your Ollama-compatible endpoint and configuration in .env.")


if __name__ == "__main__":
    main()
