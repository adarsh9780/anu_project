import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph, Checkpointer
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

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


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def echo(state: State) -> State:
    response = chat(state["messages"])
    return {"messages": [AIMessage(content=response.text)]}


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)
    builder.add_node("echo", echo)
    builder.add_edge(START, "echo")
    builder.add_edge("echo", END)

    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    # memory=MemorySaver()
    conn = sqlite3.connect("Chat_echo.db", check_same_thread=False)
    memory = SqliteSaver(conn)
    config = {"configurable": {"thread_id": "OMOMOM"}}
    graph = build_graph(checkpointer=memory)
    while True:
        msg: str = input("User: ")
        if msg == "bye":
            print("Echo:bye!")
            break
        result = graph.invoke({"messages": [HumanMessage(content=msg)]}, config=config)
        print("Echo:", result["messages"][-1].content)
