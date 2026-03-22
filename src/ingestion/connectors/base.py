"""Base connector interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawDocument:
    """Represents a raw document fetched from any source."""
    source_id: str          # Unique ID for this document
    source_name: str        # Human-readable name (e.g. filename)
    source_path: str        # Full path or URL
    source_type: str        # "pdf", "txt", "docx", "email", "confluence", etc.
    content: str            # Extracted text content
    metadata: dict = field(default_factory=dict)
    pages: list[dict] = field(default_factory=list)   # [{page_num, text}]
    tables: list[dict] = field(default_factory=list)  # [{table_index, markdown, page_num}]
    allowed_roles: list[str] = field(default_factory=lambda: ["analyst", "compliance", "operations", "admin"])
    sensitivity_level: str = "internal"


class BaseConnector(ABC):
    """Abstract base class for all source connectors."""

    @abstractmethod
    def fetch(self) -> list[RawDocument]:
        """Fetch and return documents from the source."""
        ...
