from dataclasses import dataclass, field


@dataclass
class Todo:
    id: int
    title: str
    description: str = ""
    completed: bool = False


class TodoStore:
    """In-memory todo storage."""

    def __init__(self) -> None:
        self._todos: dict[int, Todo] = {}
        self._next_id = 1

    def create(self, title: str, description: str = "") -> Todo:
        """Create a new todo item."""
        if not title.strip():
            raise ValueError("Title cannot be empty")
        todo = Todo(id=self._next_id, title=title, description=description)
        self._todos[todo.id] = todo
        self._next_id += 1
        return todo

    def list_all(self, completed: bool | None = None) -> list[Todo]:
        """List all todos, optionally filtered by completion status."""
        todos = list(self._todos.values())
        if completed is not None:
            todos = [t for t in todos if t.completed == completed]
        return todos

    def complete(self, todo_id: int) -> Todo:
        """Mark a todo as complete."""
        todo = self._todos.get(todo_id)
        if not todo:
            raise KeyError(f"Todo {todo_id} not found")
        todo.completed = True
        return todo

    def delete(self, todo_id: int) -> None:
        """Delete a todo."""
        if todo_id not in self._todos:
            raise KeyError(f"Todo {todo_id} not found")
        del self._todos[todo_id]
