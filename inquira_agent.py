import os

# some mobile hotspot like adarsh's iphone 14 plus sends ipv6, we need to force to use ipv4
os.environ["GRPC_DNS_RESOLVER"] = "native"

from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph import add_messages, StateGraph, START, END
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
)
from langgraph.graph.state import CompiledStateGraph, Checkpointer
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv

from typing import Annotated, Any, cast, Mapping
from collections.abc import Iterator

import json
from pathlib import Path


def load_json(filepath: str | Path):
    with open(filepath, "r") as file:
        schema = json.load(file)

    return schema


load_dotenv()


class MetaData(BaseModel):
    is_safe: bool | None = Field(
        default=None,
        description="if the question asked is not malicious or it cannot corrupt data",
    )
    safety_reasoning: str | None = Field(default=None)
    is_relevant: bool | None = Field(
        default=None,
        description="if the question asked is relevant to the active schema",
    )
    require_code: bool | None = Field(default=None)
    relevancy_reasoning: str | None = Field(default=None)


def merge_metadata(
    prev: MetaData | None, new: MetaData | Mapping[str, Any] | None
) -> MetaData | None:
    if new is None and prev is None:
        return None
    if prev is None:
        # First write: coerce whatever we got to MetaData
        return new if isinstance(new, MetaData) else MetaData(**(new or {}))

    # We have an existing MetaData; normalize new to dict and shallow-merge
    new_dict = new.model_dump() if isinstance(new, MetaData) else dict(new or {})
    merged = prev.model_dump() if isinstance(prev, MetaData) else dict(prev or {})
    merged.update(new_dict)
    # Re-validate to keep state as a MetaData instance
    return MetaData(**merged)


class State(BaseModel):
    messages: Annotated[list[AnyMessage], add_messages]
    metadata: Annotated[MetaData, merge_metadata] = Field(default=MetaData())
    plan: str | None = Field(default=None)
    code: str | None = Field(default=None)
    active_schema: dict[str, Any] | None = Field(
        default=load_json("deliveries_schema.json")
    )
    current_code: str = Field(
        default="", description="current code which can provide LLM more context"
    )


class InputSchema(BaseModel):
    messages: Annotated[list[AnyMessage], add_messages]
    active_schema: dict[str, Any] | None = Field(default=None)
    current_code: str = Field(
        default="", description="current code which can provide LLM more context"
    )


class OutputSchema(BaseModel):
    messages: Annotated[list[AnyMessage], add_messages]
    metadata: MetaData | None = Field(default=None)
    plan: str | None = Field(default=None)
    code: str | None = Field(default=None)


class InquiraAgent:
    def __init__(self) -> None:
        self.gemini_lite = init_chat_model("google_genai:gemini-2.5-flash-lite")
        self.gemini = init_chat_model("google_genai:gemini-2.5-flash")
        self.counter = 0

    def check_relevancy(self, state: State) -> dict[str, Any]:
        class IsRelevant(BaseModel):
            is_relevant: bool | None = Field(
                default=None,
                description="if the question asked is relevant to the active schema",
            )
            relevancy_reasoning: str | None = Field(default=None)

        system_prompt_template = SystemMessagePromptTemplate.from_template_file(
            "prompts/is_relevant_prompt.yaml", input_variables=["schema"]
        )
        prompt = ChatPromptTemplate.from_messages(
            [system_prompt_template, MessagesPlaceholder("messages")]
        )

        chain = prompt | self.gemini_lite.with_structured_output(IsRelevant)

        response = chain.invoke(
            {"messages": state.messages, "schema": state.active_schema}
        )
        response = cast(IsRelevant, response)

        return {
            "metadata": {
                "is_relevant": response.is_relevant,
                "relevancy_reasoning": response.relevancy_reasoning,
            },
            "messages": [AIMessage(content=response.relevancy_reasoning)],
        }

    def check_safety(self, state: State) -> dict[str, Any]:
        class IsSafe(BaseModel):
            is_safe: bool | None = Field(
                default=None,
                description="if the question asked is not malicious or it cannot corrupt data",
            )
            safety_reasoning: str | None = Field(default=None)

        system_prompt_template = SystemMessagePromptTemplate.from_template_file(
            "prompts/is_safe_prompt.yaml", input_variables=[]
        )
        prompt = ChatPromptTemplate.from_messages(
            [system_prompt_template, MessagesPlaceholder("messages")]
        )

        chain = prompt | self.gemini_lite.with_structured_output(IsSafe)

        response = chain.invoke({"messages": state.messages})
        response = cast(IsSafe, response)

        return {
            "metadata": {
                "is_safe": response.is_safe,
                "safety_reasoning": response.safety_reasoning,
            },
            "messages": [AIMessage(content=response.safety_reasoning)],
        }

    def require_code(self, state: State) -> dict[str, Any]:
        class RequireCode(BaseModel):
            require_code: bool | None

        system_prompt_template = SystemMessagePromptTemplate.from_template_file(
            "prompts/require_code_prompt.yaml", input_variables=["schema"]
        )
        prompt = ChatPromptTemplate.from_messages(
            [system_prompt_template, MessagesPlaceholder("messages")]
        )

        chain = prompt | self.gemini_lite.with_structured_output(RequireCode)

        response = chain.invoke(
            {"messages": state.messages, "schema": state.active_schema}
        )
        response = cast(RequireCode, response)

        return {
            "metadata": {
                "require_safe": response.require_code,
            }
        }

    def create_plan(self, state: State) -> dict[str, Any]:
        class Plan(BaseModel):
            plan: str | None

        system_prompt_template = SystemMessagePromptTemplate.from_template_file(
            "prompts/create_plan_prompt.yaml",
            input_variables=["schema", "current_code"],
        )
        prompt = ChatPromptTemplate.from_messages(
            [system_prompt_template, MessagesPlaceholder("messages")]
        )

        chain = prompt | self.gemini_lite.with_structured_output(Plan)

        response = chain.invoke(
            {
                "messages": state.messages,
                "schema": state.active_schema,
                "current_code": state.current_code,
            }
        )
        response = cast(Plan, response)

        return {"plan": response.plan}

    def code_generator(self, state: State) -> dict[str, Any]:
        class Code(BaseModel):
            code: str | None

        system_prompt_template = SystemMessagePromptTemplate.from_template_file(
            "prompts/code_prompt.yaml",
            input_variables=["plan", "current_code"],
        )
        prompt = ChatPromptTemplate.from_messages(
            [system_prompt_template, MessagesPlaceholder("messages")]
        )

        chain = prompt | self.gemini_lite.with_structured_output(Code)

        response = chain.invoke(
            {
                "messages": state.messages,
                "plan": state.plan,
                "current_code": state.current_code,
            }
        )
        response = cast(Code, response)

        return {"current_code": response.code}

    def noncode_generator(self, state: State) -> dict[str, Any]:
        system_prompt_template = SystemMessagePromptTemplate.from_template_file(
            "prompts/noncode_prompt.yaml",
            input_variables=["schema", "current_code"],
        )
        prompt = ChatPromptTemplate.from_messages(
            [system_prompt_template, MessagesPlaceholder("messages")]
        )

        chain = prompt | self.gemini

        response = chain.invoke(
            {
                "messages": state.messages,
                "schema": state.active_schema,
                "current_code": state.current_code,
            }
        )

        return {"messages": [AIMessage(content=response.content)]}

    def general_purpose(self, state: State) -> dict[str, Any]:
        system_prompt_template = """You are an helpful assistant, answer the question on less than 3 lines."""
        prompt = ChatPromptTemplate.from_messages(
            [system_prompt_template, MessagesPlaceholder("messages")]
        )

        chain = prompt | self.gemini

        response = chain.invoke({"messages": state.messages})

        return {"messages": [AIMessage(content=response.content)]}

    def unsafe_rejector(self, state: State) -> dict[str, Any]:
        return {
            "messages": [
                AIMessage(
                    content="The question is unsafe and thus will not be processed further."
                )
            ]
        }

    def compile(self, checkpointer=None) -> CompiledStateGraph:
        builder = StateGraph(
            State, input_schema=InputSchema, output_schema=OutputSchema
        )

        builder.add_node("check_relevancy", self.check_relevancy)
        builder.add_node("check_safety", self.check_safety)
        builder.add_node("require_code", self.require_code)
        builder.add_node("create_plan", self.create_plan)
        builder.add_node("code_generator", self.code_generator)
        builder.add_node("noncode_generator", self.noncode_generator)
        builder.add_node("general_purpose", self.general_purpose)
        builder.add_node("unsafe_rejector", self.unsafe_rejector)

        builder.add_edge(START, "check_safety")

        def safety_router(state: State):
            if state.metadata.is_safe:
                return "safe"
            else:
                return "unsafe"

        builder.add_conditional_edges(
            "check_safety",
            safety_router,
            {"safe": "check_relevancy", "unsafe": "unsafe_rejector"},
        )

        def relevancy_router(state: State):
            if state.metadata.is_relevant:
                return "relevant"
            else:
                return "irrelevant"

        builder.add_conditional_edges(
            "check_relevancy",
            relevancy_router,
            {"relevant": "require_code", "irrelevant": "general_purpose"},
        )

        def code_router(state: State):
            if state.metadata.require_code:
                return "yes"
            else:
                return "no"

        builder.add_conditional_edges(
            "require_code",
            code_router,
            {"yes": "create_plan", "no": "noncode_generator"},
        )

        builder.add_edge("create_plan", "code_generator")

        builder.add_edge("code_generator", END)
        builder.add_edge("general_purpose", END)
        builder.add_edge("unsafe_rejector", END)

        # builder.add_edge(["check_relevancy", "check_safety"], "router")

        # builder.add_edge("check_relevancy", END)
        # builder.add_edge("check_safety", END)

        return builder.compile(checkpointer=checkpointer)


def build_graph(checkpointer: Checkpointer) -> CompiledStateGraph:
    graph = InquiraAgent()
    agent = graph.compile(checkpointer=checkpointer)
    return agent


def execute(
    agent: CompiledStateGraph,
    user_query: str,
    thread_id: str = "adarsh9780:deliveries_schema.json",
):
    cfg: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    _, _, schema_path = thread_id.partition(":")

    if schema_path:
        active_schema = load_json(schema_path)
        state = InputSchema(
            messages=[HumanMessage(content=user_query)],
            active_schema=active_schema,
            current_code="",
        )

        state = agent.invoke(state, config=cfg)

        return state
    else:
        raise ValueError(f"no active schema is provided. current thread: {thread_id}")


def stream_nodes(
    agent: CompiledStateGraph,
    user_query: str,
    thread_id="adarsh9780:deliveries_schema.json",
) -> Iterator:
    cfg: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    _, _, schema_path = thread_id.partition(":")
    init_state = InputSchema(
        messages=[HumanMessage(content=user_query)],
        active_schema=load_json(schema_path),
        current_code="",
    )
    for step in agent.stream(init_state, config=cfg):
        for node_name, payload in step.items():
            # print("STREAM:", node_name, "keys:", list(payload.keys()))
            # print(payload["messages"])
            yield node_name, payload


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_stringify_content(part) for part in content]
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        if content.get("type") == "text":
            return content.get("text", "")
        return json.dumps(content)
    return str(content)


def convert_ai_messages_to_buffer_string(messages: list[AnyMessage]) -> str:
    msgs: list[str] = []
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            text = _stringify_content(msg.content)
            if text:
                msgs.append(text)
        else:
            break
    return "\n".join(reversed(msgs))


if __name__ == "__main__":
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langchain_core.runnables import RunnableConfig

    with SqliteSaver.from_conn_string("test.db") as memory:
        agent = build_graph(checkpointer=None)

    while True:
        user_query = input("You: ")
        if user_query in ("exit", "quit", "kill", "q", "qut", "qt", "ext"):
            break

        for node_name, payload in stream_nodes(agent, user_query):
            if "messages" in payload:
                text = convert_ai_messages_to_buffer_string(payload["messages"])
                print(f"{node_name}: {text}")
            if "plan" in payload:
                print(f"{node_name} plan:\n{payload['plan']}")
            if "code" in payload:
                print(f"{node_name} plan:\n{payload['code']}")
