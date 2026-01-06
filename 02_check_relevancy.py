from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph, Checkpointer

import random


class State(TypedDict, total=False):
    marks: int
    is_safe: bool
    is_relevant: bool
    messages: str


def check_safety(state: State) -> State:
    if state.get("marks", 0) <= 50:
        return {"is_safe": False}
    return {"is_safe": True}


def check_relevancy(state: State) -> State:
    if state.get("marks", 0) > 50:
        return {"is_relevant": True}
    return {"is_relevant": False}


def safe_node(state: State) -> State:
    return {"messages": "You passed the test and are relevant"}


def unsafe_node(state: State) -> State:
    return {"messages": "You failed the test"}


def check_safety_router(state: State):
    # this is router function, it must always return a string
    # to choose the next node
    if state.get("is_safe", False):
        return "safe"  # name of the node to go next
    return "unsafe"  # name of the node to go next


def check_relevancy_router(state: State):
    # this is router function, it must always return a string
    # to choose the next node
    if state.get("is_relevant", False):
        return "relevant"  # name of the node to go next
    return "irrelevant"  # name of the node to go next


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)
    builder.add_node("check_safety", check_safety)
    builder.add_node("check_relevancy", check_relevancy)
    builder.add_node("safe", safe_node)
    builder.add_node("unsafe", unsafe_node)

    builder.add_edge(START, "check_safety")
    builder.add_conditional_edges(
        "check_safety",
        check_safety_router,
        {"safe": "check_relevancy", "unsafe": "unsafe"},
    )
    builder.add_conditional_edges(
        "check_relevancy",
        check_relevancy_router,
        {"relevant": "safe", "irrelevant": "unsafe"},
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
