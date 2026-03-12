"""Publicador para Instagram Graph API (dos pasos: create container + publish)."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from src.publisher.base import BasePublisher

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class InstagramPublisher(BasePublisher):
    platform = "instagram"

    def __init__(self) -> None:
        self._user_id = os.environ["INSTAGRAM_USER_ID"]
        self._token = os.environ["INSTAGRAM_ACCESS_TOKEN"]

    async def publish(self, item: dict[str, Any], copy: str) -> dict[str, Any]:
        media_url = item.get("hero_media_url") or item.get("hero_image_url")
        if not media_url:
            logger.warning("Instagram: no media URL for %s, skipping", item["id"])
            return {"platform": self.platform, "remote_post_id": None, "status": "skipped"}

        params_base = {"access_token": self._token}

        async with httpx.AsyncClient() as client:
            # Paso 1: crear media container
            container_resp = await client.post(
                f"{GRAPH_API_BASE}/{self._user_id}/media",
                params={**params_base, "image_url": media_url, "caption": copy},
                timeout=30,
            )
            container_resp.raise_for_status()
            container_id = container_resp.json()["id"]

            # Paso 2: publicar el container
            publish_resp = await client.post(
                f"{GRAPH_API_BASE}/{self._user_id}/media_publish",
                params={**params_base, "creation_id": container_id},
                timeout=30,
            )
            publish_resp.raise_for_status()
            post_id = publish_resp.json().get("id", "unknown")

        logger.info("Instagram post created: %s", post_id)
        return {"platform": self.platform, "remote_post_id": post_id, "status": "published"}
