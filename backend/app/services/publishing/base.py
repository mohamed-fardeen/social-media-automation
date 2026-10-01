from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class PublisherProvider(ABC):
    platform: str = "unknown"

    @abstractmethod
    def publish(self, caption: str, image_url: Optional[str], hashtags: list) -> Dict[str, Any]:
        """Publish content. Returns {status, external_url, error}."""
        pass
