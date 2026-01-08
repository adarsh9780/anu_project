from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
import os
from google import genai
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph, Checkpointer

load_dotenv()


api_key = os.environ["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)

model = "gemini-2.5-flash-lite"


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# type annotation is changed here
def chat(user_query: list[dict]) -> str | None:
    response = client.models.generate_content(
        model=model,
        contents=user_query,
        config={
            "response_mime_type": "text/plain",
            # "response_schema": structured_output_format,
        },
    )

    return response.text


# echo is modified to convert the messages to the format expected
# by the chat function for Google Gen AI SDK
def echo(state: State) -> State:
    contents = []
    for msg in state["messages"]:
        role = "user" if isinstance(msg, HumanMessage) else "model"
        contents.append({"role": role, "parts": [{"text": msg.content}]})

    response = chat(contents)
    return {"messages": [AIMessage(content=response)]}


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)

    builder.add_node("echo", echo)

    builder.add_edge(START, "echo")
    builder.add_edge("echo", END)

    graph = builder.compile(checkpointer=checkpointer)

    return graph


if __name__ == "__main__":
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "adarsh"}}
    graph = build_graph(checkpointer=memory)
    while True:
        message = input("You: ")
        if message == "exit":
            break
        result = graph.invoke(
            {"messages": [HumanMessage(content=message)]}, config=config
        )
        # print(f"\nresults: {len(result['messages'])}")
        ai_message = result["messages"][-1]
        print("Bot: ", ai_message.content)
