"""
Sample project fixture — models.py
A class with public methods and one private method.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


class DataProcessor:
    """
    Process and transform data records.

    This class handles ingestion, normalization, and export of data records.
    It is the main workhorse of the sample project.
    """

    def __init__(self, name: str, strict: bool = False) -> None:
        """
        Initialize the DataProcessor.

        Args:
            name: A label for this processor instance.
            strict: If True, raise on any invalid record. Defaults to False.
        """
        self.name = name
        self.strict = strict
        self._records: list[dict] = []

    def load(self, records: List[dict]) -> None:
        """
        Load a list of record dicts into the processor.

        Args:
            records: List of raw record dicts to process.
        """
        self._records = records

    def process(self) -> List[dict]:
        """
        Run the processing pipeline and return normalized records.

        Returns:
            A list of normalized record dicts.
        """
        return [self._normalize(r) for r in self._records]

    def _normalize(self, record: dict) -> dict:
        """Internal normalization — should NOT appear in public symbols."""
        return {k.lower(): v for k, v in record.items()}

    def export(self, fmt: str = "json") -> str:
        """
        Export processed records to a string in the given format.

        Args:
            fmt: Output format — 'json' or 'csv'. Defaults to 'json'.

        Returns:
            A string representation of the processed records.
        """
        import json
        if fmt == "json":
            return json.dumps(self.process(), indent=2)
        raise ValueError(f"Unsupported format: {fmt!r}")


@dataclass
class Config:
    """
    Configuration dataclass for the sample project.
    """
    project_name: str
    debug: bool = False
    tags: list[str] = field(default_factory=list)
