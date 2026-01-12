from langchain.tools import tool
from tavily import TavilyClient


@tool
def get_current_datetime() -> str:
    """Get the current date and time.

    Use this tool when the user asks about the current time, date, day, or any time-related query.
    """
    from datetime import datetime

    now = datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M:%S %p")


@tool
def list_files(directory: str) -> str:
    """List all files and folders in a directory.

    Args:
        directory: Path to the directory to list. Use '~' for home directory.
                   Example: '~/Downloads', '/tmp', '.'
    """
    import os

    # Expand ~ to home directory
    expanded_path = os.path.expanduser(directory)

    if not os.path.exists(expanded_path):
        return f"Error: Directory '{directory}' does not exist."

    if not os.path.isdir(expanded_path):
        return f"Error: '{directory}' is not a directory."

    try:
        items = os.listdir(expanded_path)
        if not items:
            return f"Directory '{directory}' is empty."

        # Separate files and directories
        files = []
        dirs = []
        for item in items:
            full_path = os.path.join(expanded_path, item)
            if os.path.isdir(full_path):
                dirs.append(f"📁 {item}/")
            else:
                # Get file size
                size = os.path.getsize(full_path)
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                files.append(f"📄 {item} ({size_str})")

        result = f"Contents of '{directory}':\n"
        result += (
            f"\nDirectories ({len(dirs)}):\n" + "\n".join(sorted(dirs)) if dirs else ""
        )
        result += (
            f"\n\nFiles ({len(files)}):\n" + "\n".join(sorted(files)) if files else ""
        )
        return result

    except PermissionError:
        return f"Error: Permission denied to access '{directory}'."


@tool
def read_file(file_path: str, max_lines: int = 50) -> str:
    """Read the contents of a text file.

    Args:
        file_path: Path to the file to read. Use '~' for home directory.
        max_lines: Maximum number of lines to read (default 50 to prevent huge outputs).
    """
    import os

    expanded_path = os.path.expanduser(file_path)

    if not os.path.exists(expanded_path):
        return f"Error: File '{file_path}' does not exist."

    if os.path.isdir(expanded_path):
        return f"Error: '{file_path}' is a directory, not a file."

    try:
        with open(expanded_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            total_lines = len(lines)

            if total_lines > max_lines:
                content = "".join(lines[:max_lines])
                return f"File: {file_path} (showing first {max_lines} of {total_lines} lines)\n\n{content}\n\n... [{total_lines - max_lines} more lines]"
            else:
                return f"File: {file_path} ({total_lines} lines)\n\n{''.join(lines)}"

    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a text file (binary content)."
    except PermissionError:
        return f"Error: Permission denied to read '{file_path}'."


@tool
def get_system_info() -> str:
    """Get information about the current system including OS, Python version, and working directory.

    Use this when the user asks about the system, environment, or machine details.
    """
    import platform
    import sys
    import os

    info = []
    info.append(f"🖥️  Operating System: {platform.system()} {platform.release()}")
    info.append(f"💻 Machine: {platform.machine()}")
    info.append(f"🐍 Python Version: {sys.version.split()[0]}")
    info.append(f"📂 Current Directory: {os.getcwd()}")
    info.append(f"👤 User: {os.getenv('USER', 'Unknown')}")
    info.append(f"🏠 Home Directory: {os.path.expanduser('~')}")

    return "\n".join(info)


@tool
def search_web(query: str) -> dict:
    """
    Use this tool to search the web for information.
    """
    import os

    api_key = os.environ["TAVILY_API_KEY"]
    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, search_depth="advanced")
    return response
