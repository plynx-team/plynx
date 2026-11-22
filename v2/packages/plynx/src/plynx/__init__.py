"""PLynx engine, CLI, and server."""

try:
    from importlib.metadata import version

    __version__ = version("plynx")
except Exception:
    __version__ = "2.0.0"

__all__ = ["__version__"]
