from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    foo: int


def node1(state):
    return {"foo": state["foo"] + 1}


builder = StateGraph(State)

builder.add_node("node1", node1)

builder.add_edge(START, "node1")
builder.add_edge("node1", END)

graph = builder.compile()
result = graph.invoke({"foo": 1})
print(result)
