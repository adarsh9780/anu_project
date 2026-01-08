from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()


api_key = os.environ["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)

model = "gemini-2.5-flash-lite"


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def chat(user_query: str) -> str | None:
    response = client.models.generate_content(
        model=model,
        contents=user_query,
        config={
            "response_mime_type": "text/plain",
            # "response_schema": structured_output_format,
        },
    )

    return response.text


def echo(state: State) -> State:
    message = state["messages"][-1].content
    response = chat(message)
    return {"messages": [AIMessage(content=response)]}


builder = StateGraph(State)
builder.add_node("echo", echo)

builder.add_edge(START, "echo")
builder.add_edge("echo", END)

graph = builder.compile()
while True:
    message = input("You: ")
    if message == "exit":
        break
    result = graph.invoke({"messages": [HumanMessage(content=message)]})
    # print(f"\nresults: {len(result['messages'])}")
    ai_message = result["messages"][-1]
    print("Bot: ", ai_message.content)
