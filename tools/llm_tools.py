from dotenv import load_dotenv
load_dotenv()

from langchain_openai import AzureChatOpenAI
import os

# Shared LLM instance used by all ReAct agents
llm = AzureChatOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    temperature=0
)

def call_llm(prompt: str) -> str:
    return llm.invoke(prompt).content
