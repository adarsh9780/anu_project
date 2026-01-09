import os
from google import genai
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
client = genai.Client(api_key=api_key)

model = "gemini-2.5-flash-lite"


def chat(user_query: list[str] | str) -> str | None:
    response = client.models.generate_content(
        model=model,
        contents=user_query,
        config={
            "response_mime_type": "text/plain",
        },
    )
    return response.text


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def echo(state: State) -> State:
    contents = []
    for msg in state["messages"]:
        role = "user" if isinstance(msg, HumanMessage) else "model"
        text_content = ""
        # handle both string and list content types via content_blocks
        for block in msg.content_blocks:
            if isinstance(block, str):
                text_content += block
            elif isinstance(block, dict):
                text_content += block.get("text", "")

        contents.append({"role": role, "parts": [{"text": text_content}]})

    response = chat(contents)
    return {"messages": [AIMessage(content=response)]}


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
