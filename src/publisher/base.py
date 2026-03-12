"""Clase base para todos los publicadores de redes sociales."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BasePublisher(ABC):
    """Interfaz común para publicadores de redes sociales."""

    platform: str

    @abstractmethod
    async def publish(self, item: dict[str, Any], copy: str) -> dict[str, Any]:
        """
        Publica el content_item en la plataforma.

        Args:
            item: Documento content_item del manifest del blog.
            copy: Texto generado por CopyGenerator para esta plataforma.

        Returns:
            Dict con al menos {"platform": str, "remote_post_id": str, "status": str}.
        """
        ...
