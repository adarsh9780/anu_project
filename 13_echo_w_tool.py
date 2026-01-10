import os
import sqlite3
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import Checkpointer, CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.runnables import RunnableConfig

from tools import get_current_datetime, get_system_info, list_files, read_file

load_dotenv()
api_key = os.environ["GOOGLE_API_KEY"]

model = "gemini-2.5-flash-lite"
tools = [get_current_datetime, list_files, read_file, get_system_info]

client = init_chat_model(
    model="google_genai:gemini-3-flash-preview",  # or gpt-4.1, claude-sonnet-4-5-20250929
    api_key=api_key,
    temperature=0.7,  # Gemini 3.0+ defaults to 1.0
    max_tokens=None,
    timeout=None,
    max_retries=2,
    # other params...
)

model_with_tools = client.bind_tools(tools)


def chat(user_query: list[AnyMessage] | str) -> AnyMessage:
    response = model_with_tools.invoke(user_query)
    return response


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def echo(state: State) -> State:
    response = chat(state["messages"])
    return {"messages": [response]}


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)

    builder.add_node("echo", echo)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "echo")
    builder.add_conditional_edges("echo", tools_condition)
    builder.add_edge("tools", "echo")

    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    # memory=MemorySaver()
    conn = sqlite3.connect("chat_echo.db", check_same_thread=False)
    memory = SqliteSaver(conn)
    config: RunnableConfig = {"configurable": {"thread_id": "OMOMOM"}}
    graph = build_graph(checkpointer=memory)
    while True:
        msg: str = input("User: ")
        if msg == "bye":
            print("Echo:bye!")
            break
        result = graph.invoke({"messages": [HumanMessage(content=msg)]}, config=config)
        print("Echo:", result["messages"][-1].text)
