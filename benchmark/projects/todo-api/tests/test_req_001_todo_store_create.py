"""Tests for REQ-001: TodoStore.create."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from todo import Todo, TodoStore  # noqa: E402


def test_create_returns_todo_with_incrementing_id() -> None:
    store = TodoStore()
    t1 = store.create("Buy milk")
    t2 = store.create("Walk dog", description="Evening")
    assert isinstance(t1, Todo)
    assert t1.id == 1
    assert t1.title == "Buy milk"
    assert t1.description == ""
    assert t1.completed is False
    assert t2.id == 2
    assert t2.title == "Walk dog"
    assert t2.description == "Evening"


def test_create_rejects_blank_title() -> None:
    store = TodoStore()
    with pytest.raises(ValueError, match="Title cannot be empty"):
        store.create("")
    with pytest.raises(ValueError, match="Title cannot be empty"):
        store.create("   \t")
