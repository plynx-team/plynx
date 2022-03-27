"""Templates for PLynx Hubs and utils."""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from dataclasses_json import dataclass_json


@dataclass_json
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
    def search(self, query: Query) -> Dict[str, Any]:
        """Search for items given a query"""
