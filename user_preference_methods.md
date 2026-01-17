# User Preference Management in LangGraph

This document covers **three different methods** to persist and use user preferences in a LangGraph agent. Each method has different trade-offs and teaches different patterns.

---

## The Problem

We want our Librarian agent to:
1. **Detect** when a user expresses preferences ("I hate romance", "I love sci-fi")
2. **Store** those preferences persistently
3. **Use** them in future conversations via the system prompt

---

## Method Comparison

| Method | Complexity | Persistence | LangGraph Pattern |
|--------|------------|-------------|-------------------|
| **1: File-Based** | ⭐ Easy | ✅ Survives restarts | External storage |
| **2: Handler Node** | ⭐⭐ Medium | ⚠️ State only | Node-based processing |
| **2B: Inline Parsing** | ⭐⭐ Medium | ⚠️ State only | Echo-integrated |
| **3: InjectedState + Command** | ⭐⭐⭐ Advanced | ⚠️ State only | LangGraph native |

---

# Method 1: File-Based Storage

## Theory

The simplest approach: tool writes preferences to a JSON file, echo node reads from that file.

## Process Flow

```
User: "I hate romance novels"
        ↓
echo node: LLM decides to call update_user_preferences tool
        ↓
Tool: Reads existing prefs from file → Appends new prefs → Writes to file
        ↓
ToolMessage: "Preferences saved!"
        ↓
echo node: (next turn) Reads file → Injects into system prompt
```

## Code Implementation

### Step 1: The Tool (tools.py)

```python
import json
from langchain.tools import tool

PREFS_FILE = "user_preferences.json"

@tool
def update_user_preferences(likes: list[str] = [], dislikes: list[str] = []) -> str:
    """
    Save user's book preferences. Call this when the user expresses 
    what they like or dislike about books, genres, authors, or themes.
    
    Args:
        likes: List of things the user likes (genres, authors, themes)
        dislikes: List of things the user dislikes
    """
    # Load existing preferences
    try:
        with open(PREFS_FILE, "r") as f:
            prefs = json.load(f)
    except FileNotFoundError:
        prefs = {"likes": [], "dislikes": []}
    
    # Merge new preferences (avoid duplicates)
    prefs["likes"] = list(set(prefs["likes"] + likes))
    prefs["dislikes"] = list(set(prefs["dislikes"] + dislikes))
    
    # Save back to file
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f, indent=2)
    
    response_parts = []
    if likes:
        response_parts.append(f"you enjoy {', '.join(likes)}")
    if dislikes:
        response_parts.append(f"you're not a fan of {', '.join(dislikes)}")
    
    return f"Got it! I'll remember that {' and '.join(response_parts)}."
```

### Step 2: Helper Function to Load Preferences

```python
def load_user_preferences() -> str:
    """Load user preferences from file and format for system prompt."""
    try:
        with open(PREFS_FILE, "r") as f:
            prefs = json.load(f)
        
        parts = []
        if prefs.get("likes"):
            parts.append(f"User enjoys: {', '.join(prefs['likes'])}")
        if prefs.get("dislikes"):
            parts.append(f"User dislikes: {', '.join(prefs['dislikes'])}")
        
        return "\n".join(parts) if parts else "No preferences recorded yet."
    except FileNotFoundError:
        return "No preferences recorded yet."
```

### Step 3: Update Echo Node

```python
def echo(state: State) -> State:
    # Load preferences from file
    user_prefs = load_user_preferences()
    
    # Inject into system prompt
    system_prompt = LIBRARIAN_SYSTEM_PROMPT.format(user_preferences=user_prefs)
    system_msg = SystemMessage(content=system_prompt)
    
    summary = state.get("summary", "")
    if summary:
        messages = [system_msg, SystemMessage(content=summary)] + state.get("messages", [])
    else:
        messages = [system_msg] + state.get("messages", [])
    
    response = chat(messages)
    return {"messages": [response]}
```

### Step 4: Initialize Preferences File

Create `user_preferences.json` in your project root:
```json
{
  "likes": [],
  "dislikes": []
}
```

## Pros & Cons

| Pros | Cons |
|------|------|
| ✅ Very simple to implement | ❌ Not multi-user friendly |
| ✅ Persists across restarts | ❌ File I/O on every request |
| ✅ Easy to debug (view file) | ❌ Concurrency issues possible |
| ✅ Works with any checkpointer | ❌ Not "LangGraph native" |

## When to Use

- Prototypes and learning
- Single-user applications
- When you need restart persistence without a database

---

# Method 2: Handler Node Approach

## Theory

Tools return preference data in a recognizable format. A dedicated handler node parses tool outputs and updates graph state. The echo node reads from state.

## Process Flow

```
User: "I hate romance novels"
        ↓
echo node: LLM calls update_user_preferences("dislikes romance")
        ↓
ToolNode: Executes tool, returns "PREF_UPDATE:dislikes=romance"
        ↓
preference_handler node: Parses PREF_UPDATE, updates state["user_preferences"]
        ↓
echo node: Reads state["user_preferences"], injects into system prompt
        ↓
Response to user
```

## Graph Structure

```
                    ┌─────────────────────────────────────────────┐
                    │                                             │
                    ▼                                             │
START → check_len → echo ──[tool call]──→ ToolNode → pref_handler─┘
                    │                                         
                    └──[no tool call]──→ END
```

## Code Implementation

### Step 1: Update State Definition

```python
class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    conversation_length: int
    summary: str
    user_preferences: str  # ← Add this field
```

### Step 2: The Tool (returns parseable format)

```python
@tool
def update_user_preferences(likes: list[str] = [], dislikes: list[str] = []) -> str:
    """
    Save user's book preferences. Call when user expresses likes/dislikes.
    
    Args:
        likes: Things the user likes (genres, authors, themes)
        dislikes: Things the user dislikes
    """
    # Return in a format the handler can parse
    return f"PREF_UPDATE:likes={','.join(likes)}|dislikes={','.join(dislikes)}"
```

### Step 3: Create Handler Node

```python
def handle_preferences(state: State) -> State:
    """Parse preference updates from tool messages and update state."""
    messages = state.get("messages", [])
    current_prefs = state.get("user_preferences", "")
    
    # Look for preference updates in recent messages
    for msg in messages[-5:]:  # Check last 5 messages
        content = str(getattr(msg, "content", ""))
        
        if "PREF_UPDATE:" in content:
            # Parse the update
            update_str = content.replace("PREF_UPDATE:", "")
            parts = update_str.split("|")
            
            new_prefs = []
            for part in parts:
                if part.startswith("likes=") and part != "likes=":
                    likes = part.replace("likes=", "")
                    if likes:
                        new_prefs.append(f"Likes: {likes}")
                elif part.startswith("dislikes=") and part != "dislikes=":
                    dislikes = part.replace("dislikes=", "")
                    if dislikes:
                        new_prefs.append(f"Dislikes: {dislikes}")
            
            if new_prefs:
                # Append to existing preferences
                addition = " | ".join(new_prefs)
                updated = f"{current_prefs}\n{addition}" if current_prefs else addition
                return {"user_preferences": updated}
    
    return {}  # No updates needed
```

### Step 4: Update Echo Node

```python
def echo(state: State) -> State:
    # Get preferences from state
    user_prefs = state.get("user_preferences", "No preferences recorded yet.")
    
    # Inject into system prompt
    system_prompt = LIBRARIAN_SYSTEM_PROMPT.format(user_preferences=user_prefs)
    system_msg = SystemMessage(content=system_prompt)
    
    summary = state.get("summary", "")
    if summary:
        messages = [system_msg, SystemMessage(content=summary)] + state.get("messages", [])
    else:
        messages = [system_msg] + state.get("messages", [])
    
    response = chat(messages)
    return {"messages": [response]}
```

### Step 5: Update Graph Builder

```python
def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)

    # Add nodes
    builder.add_node("echo", echo)
    builder.add_node("check_len", check_len_node)
    builder.add_node("summarize", summarize)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("preference_handler", handle_preferences)  # ← NEW

    # Edges
    builder.add_edge(START, "check_len")
    builder.add_conditional_edges(
        "check_len", len_condition, {"echo": "echo", "summarize": "summarize"}
    )
    builder.add_edge("summarize", "echo")
    builder.add_conditional_edges("echo", tools_condition)
    
    # Updated tool flow: tools → preference_handler → echo
    builder.add_edge("tools", "preference_handler")  # ← CHANGED
    builder.add_edge("preference_handler", "echo")    # ← NEW

    return builder.compile(checkpointer=checkpointer)
```

## Pros & Cons

| Pros | Cons |
|------|------|
| ✅ Uses graph state properly | ❌ More complex graph structure |
| ✅ Preferences in checkpointer | ❌ Requires parsing logic |
| ✅ Multi-user friendly | ❌ Handler runs on EVERY tool call |
| ✅ Clean separation of concerns | ❌ Extra node in the graph |

## When to Use

- When you want state-based storage
- Multi-user applications (with proper thread_id)
- When preferences should be part of the conversation state

---

# Method 2B: Inline Parsing in Echo Node

## Theory

A simpler variation of Method 2: instead of a separate handler node, the echo node itself parses tool outputs and updates preferences. This keeps the graph simpler while still using state-based storage.

## Process Flow

```
User: "I hate romance novels"
        ↓
echo node: LLM calls update_user_preferences("dislikes romance")
        ↓
ToolNode: Executes tool, returns "PREF_UPDATE:dislikes=romance"
        ↓
echo node (on re-entry): 
    1. Parses messages for PREF_UPDATE
    2. Updates state["user_preferences"]
    3. Injects preferences into system prompt
    4. Generates response
```

## Graph Structure (Same as Original!)

```
                    ┌─────────────────────────────────┐
                    │                                 │
                    ▼                                 │
START → check_len → echo ──[tool call]──→ ToolNode ──┘
                    │                                         
                    └──[no tool call]──→ END
```

**No extra node needed!** The parsing happens inside echo.

## Code Implementation

### Step 1: Update State Definition

```python
class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    conversation_length: int
    summary: str
    user_preferences: str  # ← Add this field
```

### Step 2: The Tool (Same as Method 2)

```python
@tool
def update_user_preferences(likes: list[str] = [], dislikes: list[str] = []) -> str:
    """
    Save user's book preferences. Call when user expresses likes/dislikes.
    
    Args:
        likes: Things the user likes (genres, authors, themes)
        dislikes: Things the user dislikes
    """
    # Return in a format the echo node can parse
    return f"PREF_UPDATE:likes={','.join(likes)}|dislikes={','.join(dislikes)}"
```

### Step 3: Helper Function to Parse Preferences

```python
def parse_preference_updates(messages: list[AnyMessage], current_prefs: str) -> str:
    """
    Scan messages for PREF_UPDATE tool outputs and extract preferences.
    Returns updated preferences string.
    """
    for msg in messages[-5:]:  # Check recent messages
        content = str(getattr(msg, "content", ""))
        
        if "PREF_UPDATE:" in content:
            # Parse the update format: PREF_UPDATE:likes=a,b|dislikes=c,d
            update_str = content.replace("PREF_UPDATE:", "")
            parts = update_str.split("|")
            
            new_prefs = []
            for part in parts:
                if part.startswith("likes="):
                    likes = part.replace("likes=", "")
                    if likes:  # Not empty
                        new_prefs.append(f"Likes: {likes}")
                elif part.startswith("dislikes="):
                    dislikes = part.replace("dislikes=", "")
                    if dislikes:  # Not empty
                        new_prefs.append(f"Dislikes: {dislikes}")
            
            if new_prefs:
                addition = " | ".join(new_prefs)
                return f"{current_prefs}\n{addition}" if current_prefs else addition
    
    return current_prefs  # No changes
```

### Step 4: Update Echo Node (Does Everything!)

```python
def echo(state: State) -> State:
    messages = state.get("messages", [])
    current_prefs = state.get("user_preferences", "")
    
    # Step 1: Parse any preference updates from tool messages
    updated_prefs = parse_preference_updates(messages, current_prefs)
    
    # Step 2: Inject preferences into system prompt
    pref_text = updated_prefs if updated_prefs else "No preferences recorded yet."
    system_prompt = LIBRARIAN_SYSTEM_PROMPT.format(user_preferences=pref_text)
    system_msg = SystemMessage(content=system_prompt)
    
    # Step 3: Build message list
    summary = state.get("summary", "")
    if summary:
        full_messages = [system_msg, SystemMessage(content=summary)] + messages
    else:
        full_messages = [system_msg] + messages
    
    # Step 4: Get response
    response = chat(full_messages)
    
    # Step 5: Return updated state (preferences + new message)
    return {
        "messages": [response],
        "user_preferences": updated_prefs  # ← Update preferences in state!
    }
```

### Step 5: Graph Builder (No Changes Needed!)

```python
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
    builder.add_edge("tools", "echo")  # ← Direct connection, no handler!

    return builder.compile(checkpointer=checkpointer)
```

## Complete Example Flow

```
Turn 1:
User: "I hate romance and love mysteries"

State before echo: 
{
    messages: [HumanMessage("I hate romance...")],
    user_preferences: ""
}

echo runs → LLM calls update_user_preferences(likes=["mysteries"], dislikes=["romance"])

State after tools:
{
    messages: [
        HumanMessage("I hate romance..."),
        AIMessage(tool_calls=[...]),
        ToolMessage("PREF_UPDATE:likes=mysteries|dislikes=romance")
    ],
    user_preferences: ""
}

echo runs again:
- Parses "PREF_UPDATE:likes=mysteries|dislikes=romance"
- Updates user_preferences = "Likes: mysteries | Dislikes: romance"
- Injects into system prompt
- Generates response

State after echo:
{
    messages: [..., AIMessage("I'll remember that!")],
    user_preferences: "Likes: mysteries | Dislikes: romance"  ← Updated!
}
```

## Pros & Cons

| Pros | Cons |
|------|------|
| ✅ Simpler graph (no extra node) | ❌ Echo does multiple jobs |
| ✅ Uses graph state properly | ❌ Parsing logic in main node |
| ✅ Less files/functions | ❌ Slightly harder to test separately |
| ✅ Easy to understand flow | ❌ Must parse on EVERY echo call |

## When to Use

- When you want the simplicity of Method 2 without the extra node
- Prototypes and learning
- When you prefer "all-in-one" node design
- When you want minimal graph complexity

## Comparison: Method 2 vs 2B

| Aspect | Method 2 (Handler Node) | Method 2B (Inline) |
|--------|------------------------|-------------------|
| Graph complexity | More nodes | Fewer nodes |
| Separation of concerns | Better | Worse |
| Testing | Easier (isolated) | Harder |
| Parsing overhead | Only after tools | Every echo call |
| Code organization | Cleaner | More compact |

---

# Method 3: InjectedState + Command (LangGraph Native)

## Theory

LangGraph provides special annotations that allow tools to:
- **Read** current state via `InjectedState`
- **Write** to state via `Command`

This is the most "LangGraph native" approach and eliminates the need for a handler node.

## Key Concepts

### InjectedState
- A special annotation that injects the current graph state into a tool parameter
- The LLM does NOT see this parameter — it's hidden from the tool schema
- Allows tools to read any state field

### Command
- A special return type that tells LangGraph to update state
- Can update any state field directly
- Can also redirect to a different node with `goto`

## Process Flow

```
User: "I hate romance novels"
        ↓
echo node: LLM calls update_user_preferences(dislikes=["romance"])
        ↓
Tool receives: dislikes=["romance"] + INJECTED state (hidden from LLM)
        ↓
Tool returns: Command(update={"user_preferences": "...updated..."})
        ↓
LangGraph: Automatically updates state["user_preferences"]
        ↓
echo node: Reads state["user_preferences"], injects into system prompt
```

## Code Implementation

### Step 1: Import Required Types

```python
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing import Annotated
```

### Step 2: Update State Definition

```python
class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    conversation_length: int
    summary: str
    user_preferences: str  # ← Add this field
```

### Step 3: Create the Advanced Tool

```python
from langchain.tools import tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing import Annotated

@tool
def update_user_preferences(
    likes: list[str] = [],
    dislikes: list[str] = [],
    state: Annotated[dict, InjectedState] = None  # ← Injected by LangGraph!
) -> Command:
    """
    Save user's book preferences. Call when user expresses what they 
    like or dislike about books, genres, authors, or themes.
    
    Args:
        likes: Things the user likes (genres, authors, themes, moods)
        dislikes: Things the user dislikes or wants to avoid
    """
    # READ existing preferences from injected state
    existing_prefs = state.get("user_preferences", "") if state else ""
    
    # BUILD new preferences
    new_parts = []
    if likes:
        new_parts.append(f"Likes: {', '.join(likes)}")
    if dislikes:
        new_parts.append(f"Dislikes: {', '.join(dislikes)}")
    
    if new_parts:
        addition = " | ".join(new_parts)
        updated_prefs = f"{existing_prefs}\n{addition}" if existing_prefs else addition
    else:
        updated_prefs = existing_prefs
    
    # WRITE back to state using Command
    # Also provide a message for the conversation
    return Command(
        update={
            "user_preferences": updated_prefs,
            # Optionally add a message to confirm
            "messages": [f"I've noted your preferences: {' | '.join(new_parts)}"]
        }
    )
```

### Step 4: Update Echo Node (Same as Method 2)

```python
def echo(state: State) -> State:
    # Get preferences from state
    user_prefs = state.get("user_preferences", "No preferences recorded yet.")
    
    # Inject into system prompt
    system_prompt = LIBRARIAN_SYSTEM_PROMPT.format(user_preferences=user_prefs)
    system_msg = SystemMessage(content=system_prompt)
    
    summary = state.get("summary", "")
    if summary:
        messages = [system_msg, SystemMessage(content=summary)] + state.get("messages", [])
    else:
        messages = [system_msg] + state.get("messages", [])
    
    response = chat(messages)
    return {"messages": [response]}
```

### Step 5: Graph Structure (Simpler than Method 2!)

No need for a handler node — Command updates state automatically:

```python
def build_graph(checkpointer: Checkpointer | None = None) -> CompiledStateGraph:
    builder = StateGraph(State)

    builder.add_node("echo", echo)
    builder.add_node("check_len", check_len_node)
    builder.add_node("summarize", summarize)
    builder.add_node("tools", ToolNode(tools))  # Handles Command automatically

    builder.add_edge(START, "check_len")
    builder.add_conditional_edges(
        "check_len", len_condition, {"echo": "echo", "summarize": "summarize"}
    )
    builder.add_edge("summarize", "echo")
    builder.add_conditional_edges("echo", tools_condition)
    builder.add_edge("tools", "echo")  # Direct! No handler needed

    return builder.compile(checkpointer=checkpointer)
```

## Advanced: Using Command with goto

You can also redirect to a different node after the tool:

```python
@tool
def update_preferences_and_search(
    likes: list[str],
    search_query: str,
    state: Annotated[dict, InjectedState] = None
) -> Command:
    """Update preferences and immediately search for matching books."""
    
    # Update preferences
    existing = state.get("user_preferences", "")
    updated = f"{existing}\nLikes: {', '.join(likes)}"
    
    return Command(
        update={"user_preferences": updated},
        goto="search_node"  # ← Redirect to a different node!
    )
```

## Pros & Cons

| Pros | Cons |
|------|------|
| ✅ Most "LangGraph native" | ❌ More complex tool definition |
| ✅ No extra handler node | ❌ Requires understanding Command |
| ✅ Direct state updates | ❌ Newer API, less documentation |
| ✅ Clean and powerful | ❌ Might be overkill for simple cases |
| ✅ Supports `goto` for routing | |

## When to Use

- Production applications
- When you want clean, maintainable code
- When tools need both read AND write access to state
- When you want to leverage LangGraph's full power

---

# Implementation Checklist

## For All Methods

- [ ] Update `State` to include `user_preferences: str`
- [ ] Update `LIBRARIAN_SYSTEM_PROMPT` to use `{user_preferences}` placeholder
- [ ] Update `echo` node to inject preferences into system prompt
- [ ] Add `update_user_preferences` to your tools list

## Method 1: File-Based
- [ ] Create `user_preferences.json` with empty structure
- [ ] Create `load_user_preferences()` helper function
- [ ] Implement file-based `update_user_preferences` tool

## Method 2: Handler Node
- [ ] Create `handle_preferences` node
- [ ] Update graph to route: `tools → preference_handler → echo`
- [ ] Implement parseable-format `update_user_preferences` tool

## Method 2B: Inline Parsing
- [ ] Create `parse_preference_updates()` helper function
- [ ] Update `echo` node to call parser and return updated preferences
- [ ] Implement parseable-format `update_user_preferences` tool (same as Method 2)

## Method 3: InjectedState + Command
- [ ] Import `InjectedState` and `Command`
- [ ] Implement advanced `update_user_preferences` tool with state injection
- [ ] Ensure ToolNode handles Command returns (automatic in recent versions)

---

# Testing Your Implementation

Test with these prompts in order:

1. **Set a preference**: "I really hate romance novels"
2. **Check it remembers**: "What do you know about my reading preferences?"
3. **Add more**: "I love science fiction and dystopian books"
4. **Test recommendation**: "Recommend me a book"
5. **Verify context**: "Why did you recommend that?" (Should mention your preferences)

---

# Troubleshooting

## Preferences not updating?
- Check if the LLM is actually calling the tool (look for tool call logs)
- Make sure the tool is in your tools list
- Verify the tool docstring is clear about when to use it

## Preferences not showing in responses?
- Check if `echo` is reading from the right source (file/state)
- Print `state.get("user_preferences")` inside echo to debug
- Verify `LIBRARIAN_SYSTEM_PROMPT` has `{user_preferences}` placeholder

## Command not updating state?
- Make sure you're using recent LangGraph version (pip install -U langgraph)
- Check if ToolNode is processing the Command correctly
- Verify the return type annotation is `Command`
