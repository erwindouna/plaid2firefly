"""Exceptions that can arise"""

class Plaid2FireflyError(Exception):
    """Base class for all exceptions in this module."""

class Plaid2FireflyConnectionError(Plaid2FireflyError):
    """Exception raised for connection errors."""

class Plaid2FireflyTimeoutError(Plaid2FireflyError):
    """Exception raised for timeout errors."""

