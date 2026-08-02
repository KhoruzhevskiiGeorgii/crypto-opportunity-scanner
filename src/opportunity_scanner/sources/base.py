from datetime import datetime
from typing import Protocol

from opportunity_scanner.models import Opportunity


class SourceFetchError(RuntimeError):
    pass


class SourceAdapter(Protocol):
    name: str

    def fetch(self, *, now: datetime) -> list[Opportunity]: ...
