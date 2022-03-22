"""Templates for PLynx Hubs and utils."""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Query:
    """Hub search query entry"""
    status: str = ""
    search: str = ""
    per_page: int = 30
    offset: int = 0
    user_id: Optional[str] = None


class BaseHub:
    """Base Hub class"""
    def __init__(self):
        pass

    @abstractmethod
    def search(self, query):
        """Search for items given a query"""
