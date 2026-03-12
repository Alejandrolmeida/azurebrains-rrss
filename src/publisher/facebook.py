"""Publicador para Facebook Pages API."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from src.publisher.base import BasePublisher

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class FacebookPublisher(BasePublisher):
    platform = "facebook"

    def __init__(self) -> None:
        self._page_token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]
        self._page_id = os.environ["FACEBOOK_PAGE_ID"]

    async def publish(self, item: dict[str, Any], copy: str) -> dict[str, Any]:
        payload = {
            "message": copy,
            "link": item["canonical_url"],
            "access_token": self._page_token,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{GRAPH_API_BASE}/{self._page_id}/feed", data=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        post_id = data.get("id", "unknown")
        logger.info("Facebook post created: %s", post_id)
        return {"platform": self.platform, "remote_post_id": post_id, "status": "published"}
