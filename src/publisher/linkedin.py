"""Publicador para LinkedIn — Posts API REST."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from src.publisher.base import BasePublisher

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202311"  # Cabecera Linkedin-Version requerida


class LinkedInPublisher(BasePublisher):
    platform = "linkedin"

    def __init__(self) -> None:
        self._token = os.environ["LINKEDIN_ACCESS_TOKEN"]
        self._org_urn = os.environ["LINKEDIN_ORGANIZATION_URN"]

    async def publish(self, item: dict[str, Any], copy: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Linkedin-Version": LINKEDIN_VERSION,
        }
        payload = {
            "author": self._org_urn,
            "commentary": copy,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "content": {"article": {"source": item["canonical_url"], "title": item["title"]}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{LINKEDIN_API_BASE}/rest/posts", json=payload, headers=headers, timeout=30)
            resp.raise_for_status()

        post_id = resp.headers.get("x-restli-id", "unknown")
        logger.info("LinkedIn post created: %s", post_id)
        return {"platform": self.platform, "remote_post_id": post_id, "status": "published"}
