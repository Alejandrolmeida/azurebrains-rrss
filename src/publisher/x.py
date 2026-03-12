"""Publicador para X (Twitter) — API v2."""
from __future__ import annotations

import logging
import os
from typing import Any

import tweepy  # type: ignore[import]

from src.publisher.base import BasePublisher

logger = logging.getLogger(__name__)

# Límite de caracteres de X
X_MAX_CHARS = 280


class XPublisher(BasePublisher):
    platform = "x"

    def __init__(self) -> None:
        self._client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )

    async def publish(self, item: dict[str, Any], copy: str) -> dict[str, Any]:
        if len(copy) > X_MAX_CHARS:
            copy = copy[: X_MAX_CHARS - 1] + "…"

        response = self._client.create_tweet(text=copy)
        tweet_id = str(response.data["id"])
        logger.info("X tweet created: %s", tweet_id)
        return {"platform": self.platform, "remote_post_id": tweet_id, "status": "published"}
