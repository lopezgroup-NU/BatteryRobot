class InitializationError(Exception):
    """
    Error when initializing deck contents
    """
    pass

class ContinuableRuntimeError(Exception):
    """
    Errors that allow continuation of experiments if raised
    """
    pass


class CriticalRuntimeError(Exception):
    """
    Errors that stop continuation of experiments if raised
    """
    pass