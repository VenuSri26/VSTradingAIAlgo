"""
Minimal stdlib-only stand-in for the pieces of `pytest` that the paper-trading
test files use (pytest.raises(..., match=...)) so the suite can run in an
environment with no package-index access. Not a general pytest replacement.
"""
from __future__ import annotations
import re
import contextlib


class _RaisesContext:
    def __init__(self, expected_exception, match=None):
        self.expected_exception = expected_exception
        self.match = match
        self.exception = None

    @property
    def value(self):
        return self.exception

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(
                f"DID NOT RAISE {self.expected_exception}"
            )
        if not issubclass(exc_type, self.expected_exception):
            return False  # re-raise, wrong exception type
        if self.match is not None and not re.search(self.match, str(exc_val)):
            raise AssertionError(
                f"Pattern {self.match!r} not found in {str(exc_val)!r}"
            )
        self.exception = exc_val
        return True  # suppress the exception, it matched


def raises(expected_exception, match=None):
    return _RaisesContext(expected_exception, match=match)
