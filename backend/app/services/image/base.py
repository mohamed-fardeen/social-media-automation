from abc import ABC, abstractmethod
from typing import Optional

class ImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, width: int = 1024, height: int = 1024) -> Optional[bytes]:
        """Generate image from prompt. Returns raw image bytes or None on failure."""
        pass


class StubImageProvider(ImageProvider):
    """Stub provider when no image API is configured — returns None gracefully."""
    def generate(self, prompt: str, width: int = 1024, height: int = 1024) -> Optional[bytes]:
        from app.config.logging import logger
        logger.warning(f"[StubImageProvider] No real image provider configured. Prompt: {prompt[:80]}")
        return None
