"""Tests for REQ-004: TodoStore.delete."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from todo import TodoStore  # noqa: E402


def test_delete_removes_todo() -> None:
    store = TodoStore()
    t = store.create("Remove me")
    store.delete(t.id)
    assert store.list_all() == []


def test_delete_missing_id_raises_keyerror() -> None:
    store = TodoStore()
    with pytest.raises(KeyError, match="Todo 42 not found"):
        store.delete(42)
