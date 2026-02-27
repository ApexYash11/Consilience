"""
File System Tools for Deep Research Agent.

Enables the deep researcher to manage persistent context using the file system.
Tools include:
- write_file: Write content to a file
- read_file: Read content from a file
- append_file: Append content to a file
- list_files: List files in research context directory
- delete_file: Delete a file
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# Base directory for research context files
RESEARCH_CONTEXT_BASE = Path("./research_context")


def ensure_task_directory(task_id: UUID) -> Path:
    """Create and return the directory for a specific task's context files."""
    task_dir = RESEARCH_CONTEXT_BASE / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def get_task_file_path(task_id: UUID, filename: str) -> Path:
    """Get the full path for a task's file."""
    task_dir = ensure_task_directory(task_id)
    # Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name
    return task_dir / safe_filename


async def write_file(
    task_id: UUID,
    filename: str,
    content: str,
) -> Dict[str, Any]:
    """
    Write content to a file in the task's context directory.
    
    Args:
        task_id: Research task ID
        filename: Name of file to write
        content: Content to write
        
    Returns:
        Dict with status, filepath, and bytes_written
    """
    try:
        filepath = get_task_file_path(task_id, filename)
        
        # Write the file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        bytes_written = len(content.encode("utf-8"))
        logger.info(f"Wrote {bytes_written} bytes to {filepath}")
        
        return {
            "success": True,
            "filepath": str(filepath),
            "bytes_written": bytes_written,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to write file {filename}: {e}")
        return {
            "success": False,
            "error": str(e),
            "filename": filename,
        }


async def read_file(
    task_id: UUID,
    filename: str,
) -> Dict[str, Any]:
    """
    Read content from a file in the task's context directory.
    
    Args:
        task_id: Research task ID
        filename: Name of file to read
        
    Returns:
        Dict with status, content, and metadata
    """
    try:
        filepath = get_task_file_path(task_id, filename)
        
        if not filepath.exists():
            return {
                "success": False,
                "error": f"File not found: {filename}",
                "filepath": str(filepath),
            }
        
        # Read the file
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        stat = filepath.stat()
        logger.info(f"Read {stat.st_size} bytes from {filepath}")
        
        return {
            "success": True,
            "filepath": str(filepath),
            "content": content,
            "bytes_read": stat.st_size,
            "timestamp": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to read file {filename}: {e}")
        return {
            "success": False,
            "error": str(e),
            "filename": filename,
        }


async def append_file(
    task_id: UUID,
    filename: str,
    content: str,
) -> Dict[str, Any]:
    """
    Append content to a file in the task's context directory.
    
    Args:
        task_id: Research task ID
        filename: Name of file to append to
        content: Content to append
        
    Returns:
        Dict with status, filepath, and bytes_written
    """
    try:
        filepath = get_task_file_path(task_id, filename)
        
        # Append to the file
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content)
        
        bytes_written = len(content.encode("utf-8"))
        logger.info(f"Appended {bytes_written} bytes to {filepath}")
        
        return {
            "success": True,
            "filepath": str(filepath),
            "bytes_written": bytes_written,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to append to file {filename}: {e}")
        return {
            "success": False,
            "error": str(e),
            "filename": filename,
        }


async def list_files(
    task_id: UUID,
) -> Dict[str, Any]:
    """
    List all files in the task's context directory.
    
    Args:
        task_id: Research task ID
        
    Returns:
        Dict with status and list of files with metadata
    """
    try:
        task_dir = ensure_task_directory(task_id)
        
        files = []
        for filepath in task_dir.iterdir():
            if filepath.is_file():
                stat = filepath.stat()
                files.append({
                    "name": filepath.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        
        logger.info(f"Listed {len(files)} files in {task_dir}")
        
        return {
            "success": True,
            "directory": str(task_dir),
            "files": files,
            "count": len(files),
        }
    except Exception as e:
        logger.error(f"Failed to list files in task {task_id}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def delete_file(
    task_id: UUID,
    filename: str,
) -> Dict[str, Any]:
    """
    Delete a file in the task's context directory.
    
    Args:
        task_id: Research task ID
        filename: Name of file to delete
        
    Returns:
        Dict with status and result
    """
    try:
        filepath = get_task_file_path(task_id, filename)
        
        if not filepath.exists():
            return {
                "success": False,
                "error": f"File not found: {filename}",
            }
        
        filepath.unlink()
        logger.info(f"Deleted file {filepath}")
        
        return {
            "success": True,
            "filepath": str(filepath),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete file {filename}: {e}")
        return {
            "success": False,
            "error": str(e),
            "filename": filename,
        }


async def write_todos(
    task_id: UUID,
    todos: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Write a structured TODO list for the deep research task.
    
    This is a helper that formats a todo list and writes it to a file.
    Each todo should have: id, title, status, assigned_to
    
    Args:
        task_id: Research task ID
        todos: List of todo items
        
    Returns:
        Dict with status and filepath
    """
    try:
        # Format todos as a readable list
        todo_lines = ["# Deep Research TODO List\n"]
        for todo in todos:
            status_icon = "✓" if todo.get("status") == "completed" else "○"
            assigned = f" [{todo.get('assigned_to', 'unassigned')}]" if todo.get("assigned_to") else ""
            todo_lines.append(
                f"{status_icon} {todo.get('title', 'Untitled')}{assigned}\n"
            )
        
        # Also save as JSON for programmatic access
        json_content = json.dumps(todos, indent=2)
        
        # Write both formats
        result = await write_file(task_id, "todos.md", "".join(todo_lines))
        if result["success"]:
            await write_file(task_id, "todos.json", json_content)
        
        return result
    except Exception as e:
        logger.error(f"Failed to write todos for task {task_id}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def read_todos(
    task_id: UUID,
) -> Dict[str, Any]:
    """
    Read the structured TODO list for a deep research task.
    
    Args:
        task_id: Research task ID
        
    Returns:
        Dict with status and parsed todos
    """
    try:
        result = await read_file(task_id, "todos.json")
        
        if not result["success"]:
            return result
        
        todos = json.loads(result["content"])
        return {
            "success": True,
            "todos": todos,
            "count": len(todos),
        }
    except Exception as e:
        logger.error(f"Failed to read todos for task {task_id}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def update_todo_status(
    task_id: UUID,
    todo_id: int,
    status: str,
) -> Dict[str, Any]:
    """
    Update the status of a specific TODO item.
    
    Args:
        task_id: Research task ID
        todo_id: ID of the todo to update
        status: New status (pending, in_progress, completed)
        
    Returns:
        Dict with status and updated todos
    """
    try:
        result = await read_todos(task_id)
        
        if not result["success"]:
            return result
        
        todos = result["todos"]
        for todo in todos:
            if todo.get("id") == todo_id:
                todo["status"] = status
                break
        
        # Write back the updated todos
        write_result = await write_todos(task_id, todos)
        
        if write_result["success"]:
            return {
                "success": True,
                "todo_id": todo_id,
                "new_status": status,
                "todos": todos,
            }
        else:
            return write_result
            
    except Exception as e:
        logger.error(f"Failed to update todo status for task {task_id}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# Export all tools
FILE_SYSTEM_TOOLS = {
    "write_file": write_file,
    "read_file": read_file,
    "append_file": append_file,
    "list_files": list_files,
    "delete_file": delete_file,
    "write_todos": write_todos,
    "read_todos": read_todos,
    "update_todo_status": update_todo_status,
}
