"""
Punto de entrada del Publisher Service.

Modos de ejecución:
  - HTTP (Azure Functions / FastAPI): recibe webhooks del blog
  - CLI: publicación manual para testing
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)


async def handle_content_item(item: dict[str, Any]) -> None:
    """Procesa un content_item del manifest del blog y lo publica en todas las redes."""
    from src.db.idempotency import IdempotencyStore
    from src.formatters.copy_generator import CopyGenerator
    from src.publisher.x import XPublisher
    from src.publisher.linkedin import LinkedInPublisher
    from src.publisher.facebook import FacebookPublisher
    from src.publisher.instagram import InstagramPublisher

    store = IdempotencyStore()
    copy_gen = CopyGenerator()

    platforms = [XPublisher(), LinkedInPublisher(), FacebookPublisher(), InstagramPublisher()]

    for publisher in platforms:
        key = f"{item['id']}:{publisher.platform}"
        if await store.already_published(key):
            logger.info("Skipping %s for %s (already published)", publisher.platform, item["id"])
            continue

        copy = await copy_gen.generate(item, publisher.platform)
        result = await publisher.publish(item, copy)
        await store.record(key, result)
        logger.info("Published %s → %s: %s", item["id"], publisher.platform, result)


async def process_manifest(manifest_url: str) -> None:
    """Descarga el manifest del blog y procesa los items nuevos."""
    import httpx
    from src.db.idempotency import IdempotencyStore

    store = IdempotencyStore()
    async with httpx.AsyncClient() as client:
        resp = await client.get(manifest_url, timeout=30)
        resp.raise_for_status()
        manifest = resp.json()

    for item in manifest.get("items", []):
        if item.get("needs_review"):
            logger.info("Skipping %s (needs_review=true)", item["id"])
            continue
        await handle_content_item(item)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Azurebrains RRSS Publisher")
    parser.add_argument("--manifest-url", default=os.getenv("BLOG_MANIFEST_URL"))
    parser.add_argument("--item-json", help="JSON de un content_item para publicar directamente")
    args = parser.parse_args()

    if args.item_json:
        item = json.loads(args.item_json)
        asyncio.run(handle_content_item(item))
    elif args.manifest_url:
        asyncio.run(process_manifest(args.manifest_url))
    else:
        print("Error: --manifest-url o --item-json requerido")
        sys.exit(1)
