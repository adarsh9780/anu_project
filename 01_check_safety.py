from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph, Checkpointer

import random


class State(TypedDict, total=False):
    marks: int
    is_safe: bool
    messages: str


def check_safety(state: State) -> State:
    if state.get("marks", 0) >= 50:
        return {"is_safe": True}
    return {"is_safe": False}


def safe_node(state: State) -> State:
    return {"messages": "You passed the test"}


def unsafe_node(state: State) -> State:
    return {"messages": "You failed the test"}


def check_safety_router(state: State):
    # this is router function, it must always return a string
    # to choose the next node
    if state.get("is_safe", False):
        return "safe"  # name of the node to go next
    return "unsafe"  # name of the node to go next


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)
    builder.add_node("check_safety", check_safety)
    builder.add_node("safe", safe_node)
    builder.add_node("unsafe", unsafe_node)

    builder.add_edge(START, "check_safety")
    builder.add_conditional_edges(
        "check_safety", check_safety_router, {"safe": "safe", "unsafe": "unsafe"}
    )
    builder.add_edge("safe", END)
    builder.add_edge("unsafe", END)

    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    graph = build_graph()
    marks = random.randint(0, 100)
    print(f"Marks: {marks}")
    result = graph.invoke({"marks": marks})
    print(f"Result: {result['messages']}")
