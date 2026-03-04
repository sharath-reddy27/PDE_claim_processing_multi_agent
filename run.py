import load_env  # Ensure environment variables are loaded from .env
import os

print("DEBUG: Endpoint:", os.getenv("AZURE_OPENAI_ENDPOINT"))
print("DEBUG: API key set?", bool(os.getenv("AZURE_OPENAI_API_KEY")))
print("DEBUG: AD token set?", bool(os.getenv("AZURE_OPENAI_AD_TOKEN")))
print("DEBUG: API version:", os.getenv("AZURE_OPENAI_API_VERSION"))
print("DEBUG: Chat deployment:", os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"))

from graph import build_graph
app = build_graph()

initial_state = {
    "claim_id":"C001",
    "error_code":"781"
}

result = app.invoke(initial_state)

print("\n FINAL RESULT: ")
print(result)

