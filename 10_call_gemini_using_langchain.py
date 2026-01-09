from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, AnyMessage
from dotenv import load_dotenv
import os


load_dotenv()
api_key = os.environ["GOOGLE_API_KEY"]

model = "gemini-2.5-flash-lite"

client = ChatGoogleGenerativeAI(
    model=model,
    api_key=api_key,
    temperature=0.7,  # Gemini 3.0+ defaults to 1.0
    max_tokens=None,
    timeout=None,
    max_retries=2,
    # other params...
)


def chat(user_query: list[AnyMessage] | str) -> AIMessage:
    response = client.invoke(user_query)
    return response


if __name__ == "__main__":
    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="What is the capital of France?"),
    ]
    response = chat(messages)
    print(response.text)
