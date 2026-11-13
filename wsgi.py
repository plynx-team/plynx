#!/usr/bin/env python
"""WSGI entrypoint."""
from plynx.web import app, run_api

if __name__ == "__main__":
    run_api(verbose=0)
