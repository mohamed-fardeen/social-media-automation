from typing import Dict, Any, Optional, List
import httpx
from app.services.publishing.base import PublisherProvider
from app.config.settings import settings
from app.config.logging import logger


class InstagramProvider(PublisherProvider):
    platform = "instagram"

    def __init__(self):
        self.access_token = settings.INSTAGRAM_ACCESS_TOKEN
        self.account_id = settings.INSTAGRAM_BUSINESS_ACCOUNT_ID
        self.available = bool(self.access_token and self.account_id)
        if not self.available:
            logger.warning("Instagram credentials not configured. Publishing will be simulated.")

    def publish(self, caption: str, image_url: Optional[str], hashtags: List[str]) -> Dict[str, Any]:
        if not self.available:
            logger.info("[InstagramProvider] Simulating publish (no credentials).")
            return {"status": "simulated", "external_url": None, "error": None}

        try:
            full_caption = caption
            if hashtags:
                full_caption += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

            # Step 1: Create media container
            container_url = f"https://graph.facebook.com/v19.0/{self.account_id}/media"
            payload: Dict[str, Any] = {
                "caption": full_caption,
                "access_token": self.access_token
            }
            if image_url:
                payload["image_url"] = image_url
                payload["media_type"] = "IMAGE"

            with httpx.Client(timeout=30) as client:
                res = client.post(container_url, json=payload)
                res.raise_for_status()
                creation_id = res.json().get("id")

                # Step 2: Publish the container
                publish_url = f"https://graph.facebook.com/v19.0/{self.account_id}/media_publish"
                pub_res = client.post(publish_url, json={
                    "creation_id": creation_id,
                    "access_token": self.access_token
                })
                pub_res.raise_for_status()
                post_id = pub_res.json().get("id")

            return {
                "status": "success",
                "external_url": f"https://www.instagram.com/p/{post_id}/",
                "error": None
            }
        except Exception as e:
            logger.error(f"Instagram publish failed: {e}")
            return {"status": "failed", "external_url": None, "error": str(e)}
