"""Placeholder test so the test suite is wired up from the first commit."""

import plynx
import plynx_sdk
import standard_io


def test_packages_import() -> None:
    """All workspace members are installed and importable."""
    assert plynx.__doc__
    assert plynx_sdk.__doc__
    assert standard_io.__doc__
