from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph, Checkpointer


class State(TypedDict):
    foo: int


def node1(state):
    return {"foo": state["foo"] + 1}


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)

    builder.add_node("node1", node1)

    builder.add_edge(START, "node1")
    builder.add_edge("node1", END)

    graph = builder.compile()

    return graph


if __name__ == "__main__":
    graph = build_graph()
    result = graph.invoke({"foo": 1})
    print(result)
