from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph, Checkpointer


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def echo(state: State) -> State:
    message = state["messages"][-1].content
    return {"messages": [AIMessage(content=message)]}


def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)

    builder.add_node("echo", echo)

    builder.add_edge(START, "echo")
    builder.add_edge("echo", END)

    graph = builder.compile()

    return graph


if __name__ == "__main__":
    graph = build_graph()
    while True:
        message = input("You: ")
        if message == "exit":
            break
        result = graph.invoke({"messages": [HumanMessage(content=message)]})
        print(f"\nresults: {len(result['messages'])}")
        ai_message = result["messages"][-1]
        print("Bot: ", ai_message.content)
