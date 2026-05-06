# Todo API Requirements

## REQ-001: Create Todo
Users must be able to create a new todo item.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Todo has a title and optional description
  - New todos default to incomplete status
  - Created todo is returned with an ID

## REQ-002: List Todos
Users must be able to list all todo items.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Returns all todos
  - Supports filtering by completion status

## REQ-003: Complete Todo
Users must be able to mark a todo as complete.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Todo status changes to complete
  - Completing an already complete todo is idempotent

## REQ-004: Delete Todo
Users must be able to delete a todo item.
- Priority: Medium
- Type: Functional
- Acceptance Criteria:
  - Todo is removed from the list
  - Deleting non-existent todo returns appropriate error
