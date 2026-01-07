from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph, Checkpointer

import random


class State(TypedDict, total=False):
    marks: int
    is_safe: bool
    messages: str


# Nodes Defintion
def check_safety(state: State) -> State:
    if state.get("marks", 0) >= 50:
        return {"is_safe": True}
    return {"is_safe": False}


def safe_node(state: State) -> State:
    return {"messages": "You passed the test"}


def unsafe_node(state: State) -> State:
    return {"messages": "You failed the test"}


# routers function
def check_safety_router(state: State) -> str:
    if state.get("is_safe"):
        return "anu"
    return "adarsh"


builder = StateGraph(State)

# add nodes
builder.add_node("check_safety", check_safety)
builder.add_node("safe_node", safe_node)
builder.add_node("unsafe_node", unsafe_node)

# connect nodes
builder.add_edge(START, "check_safety")
builder.add_conditional_edges(
    "check_safety", check_safety_router, {"anu": "safe_node", "adarsh": "unsafe_node"}
)
builder.add_edge("safe_node", END)
builder.add_edge("unsafe_node", END)

graph = builder.compile()

marks = random.randint(0, 100)
print(f"Marks: {marks}")
result = graph.invoke({"marks": marks})

print(f"State: {result}")
print(f"Result: {result['messages']}")
