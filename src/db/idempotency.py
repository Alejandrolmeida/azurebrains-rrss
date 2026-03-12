"""Capa de idempotencia sobre Cosmos DB para evitar publicaciones duplicadas."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

logger = logging.getLogger(__name__)


class IdempotencyStore:
    """
    Registra y verifica publicaciones en la colección 'rrss' de Cosmos DB.

    Usa como clave de idempotencia: ``"{content_item_id}:{platform}"``.
    """

    def __init__(self) -> None:
        endpoint = os.environ["COSMOS_ENDPOINT"]
        key = os.environ.get("COSMOS_KEY")  # None si se usa Managed Identity
        self._client = CosmosClient(endpoint, credential=key)
        self._db_name = os.getenv("COSMOS_DATABASE", "chatdb")
        self._container_name = os.getenv("COSMOS_CONTAINER_RRSS", "rrss")

    async def already_published(self, idempotency_key: str) -> bool:
        """Devuelve True si la clave ya existe en Cosmos DB."""
        try:
            container = self._client.get_database_client(self._db_name).get_container_client(self._container_name)
            item = await container.read_item(idempotency_key, partition_key=idempotency_key)
            return item.get("status") == "published"
        except CosmosResourceNotFoundError:
            return False

    async def record(self, idempotency_key: str, result: dict[str, Any]) -> None:
        """Registra el resultado de una publicación en Cosmos DB."""
        container = self._client.get_database_client(self._db_name).get_container_client(self._container_name)
        doc = {
            "id": idempotency_key,
            "type": "delivery_job",
            **result,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        await container.upsert_item(doc)
        logger.debug("Recorded delivery job: %s", idempotency_key)
