import os
from dotenv import load_dotenv
from tools import get_current_datetime, list_files, read_file, get_system_info
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, ToolMessage
from langchain.chat_models import init_chat_model

load_dotenv()
api_key = os.environ["GOOGLE_API_KEY"]

# Define tools and create lookup map
tools = [get_current_datetime, list_files, read_file, get_system_info]
tool_map = {tool.name: tool for tool in tools}

client = init_chat_model(
    model="google_genai:gemini-2.5-flash-lite",
    api_key=api_key,
    temperature=0.7,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# Bind tools to the model
model_with_tools = client.bind_tools(tools)


def chat(user_query: str) -> str:
    """Chat with tool execution support."""
    messages = [HumanMessage(content=user_query)]

    # First LLM call - may return tool calls
    response = model_with_tools.invoke(messages)

    # If no tool calls, return the response directly
    if not response.tool_calls:
        return response.content

    # Add AI response (with tool calls) to message history
    messages.append(response)

    # Execute each tool and collect results
    for tool_call in response.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        print(f"  🔧 Calling tool: {tool_name}({tool_args})")

        # Execute the tool
        tool_result = tool_map[tool_name].invoke(tool_args)

        # Add tool result to messages
        messages.append(
            ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"])
        )

    # Second LLM call - uses tool results to form final answer
    final_response = model_with_tools.invoke(messages)
    return final_response.content


def chat(user_query: list[AnyMessage] | str) -> AIMessage:
    response = model_with_tools.invoke(user_query)
    return response


if __name__ == "__main__":
    while True:
        user_query = input("User: ")
        if user_query.lower() == "bye":
            print("Echo: bye!")
            break
        response = chat(user_query)
        print("Echo: ", response)
