# Calculator Requirements

## REQ-001: Basic Addition
The calculator must support adding two numbers.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Adding 2 + 3 returns 5
  - Adding negative numbers works correctly
  - Adding floats works correctly

## REQ-002: Basic Subtraction
The calculator must support subtracting two numbers.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Subtracting 5 - 3 returns 2
  - Subtracting to get negative results works

## REQ-003: Multiplication
The calculator must support multiplying two numbers.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Multiplying 3 * 4 returns 12
  - Multiplying by zero returns 0

## REQ-004: Division
The calculator must support dividing two numbers.
- Priority: High
- Type: Functional
- Acceptance Criteria:
  - Dividing 10 / 2 returns 5
  - Division by zero raises an appropriate error

## REQ-005: Input Validation
The calculator must validate that inputs are numbers.
- Priority: Medium
- Type: Non-functional
- Acceptance Criteria:
  - Non-numeric input raises ValueError
  - None input raises TypeError
