from core.orchestrator import Orchestrator
from core.schemas import ChatRequest
import asyncio

async def chat_loop() -> None:
    orchestrator = Orchestrator()

    print("LLM Guardrails CLI started. Type 'exit' or 'quit' to stop.")

    while True:
        text = input("\nUser> ").strip()

        if text.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        if not text:
            continue

        request = ChatRequest(user_id="cli_user", text=text)
        response = await orchestrator.process(request)

        print("\nGuardrails:")
        print(f"  request_id: {response.request_id}")
        print(f"  action: {response.action}")
        print(f"  risk_score: {response.risk_score}")
        print(f"  message: {response.message}")

        print("\nLLM:")
        print(response.llm_response or "<no LLM response>")


if __name__ == "__main__":
    asyncio.run(chat_loop())
