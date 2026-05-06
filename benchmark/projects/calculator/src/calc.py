class Calculator:
    """A simple calculator supporting basic arithmetic operations."""

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        self._validate(a, b)
        return a + b

    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        self._validate(a, b)
        return a - b

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        self._validate(a, b)
        return a * b

    def divide(self, a: float, b: float) -> float:
        """Divide a by b."""
        self._validate(a, b)
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return a / b

    def _validate(self, *args: float) -> None:
        """Validate that all arguments are numbers."""
        for arg in args:
            if arg is None:
                raise TypeError("Input cannot be None")
            if not isinstance(arg, (int, float)):
                raise ValueError(f"Expected a number, got {type(arg).__name__}")
