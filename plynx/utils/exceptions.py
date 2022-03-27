"""Standard PLynx Exceptions"""


class ExecutorNotFound(ImportError):
    """Executor not imported"""


class RegisterUserException(Exception):
    """Failed to register the user"""
    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
