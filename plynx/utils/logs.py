"""Logging utils"""

import logging


def set_logging_level(verbose: int, logger=None):
    """Set logging level based on integer"""
    if logger is None:
        logger = logging.getLogger()
    levels = {
        0: logging.CRITICAL,
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO,
        4: logging.DEBUG
    }
    logger.setLevel(levels.get(verbose, logging.DEBUG))
