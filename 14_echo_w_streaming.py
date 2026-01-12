import os
import sqlite3
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
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
            print("Echo: bye!")
            break
        # current: invoke waits for the graph to finish and then returns the final result
        # result = graph.invoke({"messages": [HumanMessage(content=msg)]}, config=config)
        # print("Echo:", result["messages"][-1].text)

        # Method 1: Using .stream()
        # Using .stream() allows us to process the graph's execution in real-time.
        # It returns an iterator that yields the output of each node immediately after it finishes
        # rather than waiting for the entire graph to complete.
        # State Tracking: This allows us to see exactly how the state changes at every step of the workflow.
        # result = graph.stream({"messages": [HumanMessage(content=msg)]}, config=config)
        # for chunk in result:
        #     for node_name, updates in chunk.items():
        #         print("Node Name: ", node_name)
        #         print("Updates: ", updates.get("messages", []))
        #         print("\n")

        # print("\n--- AI IS THINKING ---\n")

        for mode, chunk in graph.stream(
            {"messages": [HumanMessage(content=msg)]},
            config=config,
            stream_mode=["messages", "updates"],
        ):
            # Handle Text Streaming (The "Pretty" Part)
            if mode == "messages":
                message, metadata = chunk
                # We only care about the final response from the model, not intermediate tool calls
                if isinstance(message, AIMessage) and not message.tool_calls:
                    if message.content:
                        # Handle string content
                        if isinstance(message.content, str):
                            print(message.content, end="", flush=True)
                        # Handle complex content (Gemini)
                        elif isinstance(message.content, list):
                            for part in message.content:
                                if isinstance(part, dict) and "text" in part:
                                    print(part["text"], end="", flush=True)

            # Handle State Updates (The "Logic" Part)
            elif mode == "updates":
                for node_name, updates in chunk.items():
                    # If the AI decided to call a tool
                    if node_name == "echo" and "messages" in updates:
                        last_msg = updates["messages"][-1]
                        if last_msg.tool_calls:
                            print(
                                f"\n[AI is calling tools: {[t['name'] for t in last_msg.tool_calls]}]"
                            )

                    # If a tool finished running
                    if node_name == "tools" and "messages" in updates:
                        for tool_msg in updates["messages"]:
                            print(f"\n[Tool '{tool_msg.name}' returned result]")
        print("\n\n--- DONE ---")

        # Method 1a: Using .stream() with "stream_mode" parameter
        # result = graph.stream(
        #     {"messages": [HumanMessage(content=msg)]},
        #     config=config,
        #     stream_mode="updates",
        # )
        # for message, metadata in result:
        #     if message.content:
        #         if isinstance(message.content, str):
        #             print(message.content, end="|", flush=True)

        #         elif isinstance(message.content, list):
        #             for part in message.content:
        #                 if isinstance(part, dict) and "text" in part:
        #                     print(part["text"], end="", flush=True)
        #                 elif isinstance(part, str):
        #                     print(part, end="", flush=True)
        # print()
