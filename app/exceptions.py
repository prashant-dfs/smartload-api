class ValidationError(Exception):
    """Raised when request payload fails business validation."""
    pass


class PayloadTooLargeError(Exception):
    """Raised when there are too many orders (> 22)."""
    pass


class NoFeasibleCombinationError(Exception):
    """Raised when no combination of orders fits within truck constraints."""
    pass
