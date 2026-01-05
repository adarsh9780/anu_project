import os
import sqlite3
from dataclasses import dataclass
from typing import Annotated, Literal, Sequence

from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from python_tool import execute_python


class SafetyCheckResponse(BaseModel):
    is_safe: bool = Field(
        default=True, description="if the user query is safe for kids under 18"
    )
    nature: Literal["education", "entertainment"] = Field(
        description="if the nature of the query asked by the user is educative or for entertainment"
    )


# slots = True = immutable dictionary
@dataclass(slots=True)
class State:
    conversation: Annotated[Sequence[BaseMessage], add_messages]


# class State(TypedDict):
#     conversation: Annotated[Sequence[BaseMessage], add_messages]


def llm_node(state: State) -> dict:
    # response = model_w_tools.invoke(state["conversation"])
    response = model_w_tools.invoke(state.conversation)
    return {"conversation": [response]}


load_dotenv()

conn = sqlite3.connect("chathistory.db", check_same_thread=False)
memory = SqliteSaver(conn)

# tools = [basic_calculator, current_time, current_date, current_datetime, local_timezone]
tools = [execute_python]
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", temperature=0, api_key=os.getenv("GEMINI_API_KEY")
)

model_w_tools = model.bind_tools(tools, parallel_tool_calls=False)
model_w_strop = model.with_structured_output(SafetyCheckResponse)


builder = StateGraph(State)

# add nodes
builder.add_node("llm_node", llm_node)
builder.add_node("tools", ToolNode(tools, messages_key="conversation"))

# connect nodes to edges
builder.add_edge(START, "llm_node")
builder.add_edge("llm_node", END)
builder.add_conditional_edges(
    "llm_node",
    lambda state: tools_condition(state, messages_key="conversation"),
    {"tools": "tools", "__end__": "__end__"},
)
builder.add_edge("tools", "llm_node")
builder.add_edge("llm_node", END)

# compile the graph
py_graph = builder.compile()


def ensure_system_prompt(
    graph: CompiledStateGraph, config: RunnableConfig, system_prompt: str
):
    state = graph.get_state(config)
    messages = state.values.get("conversation", [])
    has_system_prompt = any(
        getattr(msg, "type", None) == "system"
        or msg.__class__.__name__ == "SystemMessage"
        for msg in messages
    )
    if not has_system_prompt:
        print("first time user, initializing...")
        graph.update_state(
            config, State(conversation=[SystemMessage(content=system_prompt)])
        )

    return graph


if __name__ == "__main__":
    graph = builder.compile(checkpointer=memory)

    env = Environment(loader=FileSystemLoader("prompts"))
    system_prompt = env.get_template("system_prompt.jinja").render()

    # Specify a thread
    config: RunnableConfig = {"configurable": {"thread_id": "5"}}

    graph = ensure_system_prompt(graph, config, system_prompt)
    while True:
        user_query = input("\nYou: ")
        if user_query == "exit":
            break
        conversation = [HumanMessage(content=user_query)]
        # state = graph.invoke({"conversation": conversation}, config)
        state = graph.invoke(State(conversation=conversation), config)

        print(f"\nState: \t{state['conversation'][-1].content}")
