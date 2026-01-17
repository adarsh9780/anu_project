import os
import sqlite3
from typing import Annotated, TypedDict
import json

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages, RemoveMessage
from langgraph.graph.state import Checkpointer, CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.runnables import RunnableConfig

from tools import (
    get_current_datetime,
    get_system_info,
    list_files,
    read_file,
    search_web,
    update_user_preferences,
)
from prompts import LIBRARIAN_SYSTEM_PROMPT

load_dotenv()
api_key = os.environ["GOOGLE_API_KEY"]

model = "gemini-2.5-flash-lite"
tools = [
    get_current_datetime,
    list_files,
    read_file,
    get_system_info,
    search_web,
    update_user_preferences,
]

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


def create_summary(messages: list[AnyMessage]) -> AnyMessage:
    prompt = f"""
    Summarize the following conversation. Make sure redundancy is removed.
    {messages}
    """
    response = chat(prompt)
    return response


def get_safe_trim_index(messages: list[AnyMessage], keep_last_n: int = 5) -> int:
    """
    Find the safe index to start keeping messages from.
    Ensures we start with a HumanMessage and don't break tool chains.
    """
    # We want to keep at least the last `keep_last_n` messages
    candidate_index = len(messages) - keep_last_n

    if candidate_index <= 0:
        return 0  # Not enough to trim

    # Walk forward until we find a HumanMessage
    for i in range(candidate_index, len(messages)):
        if isinstance(messages[i], HumanMessage):
            return i  # Safe to trim everything before this

    # If no HumanMessage found in the window, don't trim at all
    return 0


class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    user_preferences: dict[str, list[str]]
    conversation_length: int
    summary: str


def check_len_node(state: State) -> State:
    cl = len(state.get("messages", []))
    return {"conversation_length": cl}


def load_user_preference(state: State) -> dict[str, list[str]]:
    existing_user_preferences = state.get(
        "user_preferences", {"likes": [], "dislikes": []}
    )

    recent_messages = state.get("messages", [])[-5:]
    for message in recent_messages:
        if (
            isinstance(message, ToolMessage)
            and message.name == "update_user_preferences"
        ):
            content = str(message.content)

            if not content.startswith("PREF_UPDATE:"):
                continue

            try:
                updated_str = content.replace("PREF_UPDATE:", "")
                prefs = json.loads(updated_str)

                likes = set(
                    existing_user_preferences.get("likes", []) + prefs.get("likes", [])
                )
                dislikes = set(
                    existing_user_preferences.get("dislikes", [])
                    + prefs.get("dislikes", [])
                )

                existing_user_preferences["likes"] = list(likes)
                existing_user_preferences["dislikes"] = list(dislikes)
            except json.JSONDecodeError:
                continue  # Skip if parsing fails

    return existing_user_preferences


def echo(state: State) -> State:
    messages = state.get("messages", [])

    user_preferences = load_user_preference(state)

    system_msg = SystemMessage(
        content=LIBRARIAN_SYSTEM_PROMPT.format(user_preferences=user_preferences)
    )
    summary = state.get("summary", "")
    if summary:
        messages = [system_msg, SystemMessage(content=summary)] + state.get(
            "messages", []
        )
        response = chat(messages)
    else:
        messages = [system_msg] + state.get("messages", [])
        response = chat(messages)
    return {"messages": [response], "user_preferences": user_preferences}


def summarize(state: State) -> State:
    messages = state.get("messages", [])
    existing_summary = state.get("summary", "")
    safe_index = get_safe_trim_index(messages)
    if (len(messages) > 10) and (safe_index > 0):
        messages_to_delete = messages[:safe_index]
        conversation_to_summarize = [
            SystemMessage(content=existing_summary)
        ] + messages_to_delete
        summary = create_summary(conversation_to_summarize)
        summary = existing_summary + "\n" + summary.text
        summary = f"Here is the conversation summary so far: {summary}"

        # step 2: delete all messages except last n
        delete_messages = [RemoveMessage(id=m.id) for m in messages_to_delete]

        return {"messages": delete_messages, "summary": summary}
    else:
        return {}  # to make no changes to the state


def len_condition(state: State) -> str:
    if state.get("conversation_length", 0) > 10:
        return "summarize"
    return "echo"


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)

    builder.add_node("echo", echo)
    builder.add_node("check_len", check_len_node)
    builder.add_node("summarize", summarize)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "check_len")
    builder.add_conditional_edges(
        "check_len", len_condition, {"echo": "echo", "summarize": "summarize"}
    )

    builder.add_edge("summarize", "echo")
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

        print("\n--- Kautilya IS THINKING ---\n")

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
                    if metadata.get("langgraph_node") in ["check_len", "summarize"]:
                        continue

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
                    if node_name == "summarize":
                        print("\n[Kautilya is summarizing the conversation]")
                    # If the AI decided to call a tool
                    if node_name == "echo" and "messages" in updates:
                        last_msg = updates["messages"][-1]
                        if last_msg.tool_calls:
                            print(
                                f"\n[Kautilya is calling tools: {[t['name'] for t in last_msg.tool_calls]}]"
                            )

                    # If a tool finished running
                    if node_name == "tools" and "messages" in updates:
                        for tool_msg in updates["messages"]:
                            print(f"\n[Tool '{tool_msg.name}' returned result]")
        print("\n\n--- DONE ---")
