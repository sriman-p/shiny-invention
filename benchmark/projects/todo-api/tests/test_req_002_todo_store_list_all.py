"""Tests for REQ-002: TodoStore.list_all."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from todo import TodoStore  # noqa: E402


def test_list_all_empty_store() -> None:
    assert TodoStore().list_all() == []


def test_list_all_returns_all_todos_when_no_filter() -> None:
    store = TodoStore()
    a = store.create("A")
    b = store.create("B")
    todos = store.list_all()
    assert {t.id for t in todos} == {a.id, b.id}


def test_list_all_filters_by_completion() -> None:
    store = TodoStore()
    store.create("Open")
    done = store.create("Done")
    store.complete(done.id)
    completed = store.list_all(completed=True)
    incomplete = store.list_all(completed=False)
    assert len(completed) == 1
    assert completed[0].id == done.id
    assert completed[0].completed is True
    assert len(incomplete) == 1
    assert incomplete[0].completed is False
