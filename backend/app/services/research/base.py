from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.schemas.research_plan import ResearchDocument

class BaseResearchProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name identifier of the research provider."""
        pass

    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[ResearchDocument]:
        """Search and return list of normalized ResearchDocument objects."""
        pass

# Alias for backward compatibility
ResearchProvider = BaseResearchProvider

