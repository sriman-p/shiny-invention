"""Tests for REQ-003: TodoStore.complete."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from todo import TodoStore  # noqa: E402


def test_complete_marks_todo_completed_and_returns_same_instance() -> None:
    store = TodoStore()
    t = store.create("Task")
    assert t.completed is False
    updated = store.complete(t.id)
    assert updated is t
    assert updated.completed is True
    assert store.list_all()[0].completed is True


def test_complete_missing_id_raises_keyerror() -> None:
    store = TodoStore()
    with pytest.raises(KeyError, match="Todo 999 not found"):
        store.complete(999)
