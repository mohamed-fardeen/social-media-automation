from typing import Dict, Any, Optional, List
import httpx
from app.services.publishing.base import PublisherProvider
from app.config.settings import settings
from app.config.logging import logger


class LinkedInProvider(PublisherProvider):
    platform = "linkedin"

    def __init__(self):
        self.access_token = settings.LINKEDIN_ACCESS_TOKEN
        self.org_id = settings.LINKEDIN_ORGANIZATION_ID
        self.available = bool(self.access_token)
        if not self.available:
            logger.warning("LinkedIn credentials not configured. Publishing will be simulated.")

    def publish(self, caption: str, image_url: Optional[str], hashtags: List[str]) -> Dict[str, Any]:
        if not self.available:
            logger.info("[LinkedInProvider] Simulating publish (no credentials).")
            return {"status": "simulated", "external_url": None, "error": None}

        try:
            full_text = caption
            if hashtags:
                full_text += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

            author = f"urn:li:organization:{self.org_id}" if self.org_id else "urn:li:person:me"

            post_body: Dict[str, Any] = {
                "author": author,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": full_text},
                        "shareMediaCategory": "NONE" if not image_url else "IMAGE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            with httpx.Client(timeout=30) as client:
                response = client.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    json=post_body,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0"
                    }
                )
                response.raise_for_status()
                post_id = response.json().get("id", "")

            return {
                "status": "success",
                "external_url": f"https://www.linkedin.com/feed/update/{post_id}/",
                "error": None
            }
        except Exception as e:
            logger.error(f"LinkedIn publish failed: {e}")
            return {"status": "failed", "external_url": None, "error": str(e)}
