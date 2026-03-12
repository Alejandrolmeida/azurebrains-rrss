"""Generador de copy por plataforma usando Azure OpenAI gpt-4o-mini."""
from __future__ import annotations

import logging
import os
from typing import Any

from openai import AsyncAzureOpenAI

logger = logging.getLogger(__name__)

_PROMPTS: dict[str, str] = {
    "x": (
        "Genera un tweet en español para anunciar el siguiente artículo técnico de Azure. "
        "Incluye 3-4 hashtags relevantes al final. Máximo 280 caracteres totales. "
        "Tono profesional y cercano. Termina siempre con la URL del artículo.\n\n"
        "Título: {title}\nResumen: {excerpt}\nURL: {url}"
    ),
    "linkedin": (
        "Genera un post para LinkedIn en español para anunciar el siguiente artículo técnico de Azure. "
        "Empieza con un hook que capture la atención. Desarrollo en 2-3 párrafos cortos. "
        "Termina con una pregunta o CTA. Incluye 5-8 hashtags al final. "
        "Tono experto pero accesible. Entre 800 y 1.500 caracteres.\n\n"
        "Título: {title}\nResumen: {excerpt}\nURL: {url}"
    ),
    "facebook": (
        "Genera un post para Facebook en español para anunciar el siguiente artículo técnico de Azure. "
        "Tono más informal que LinkedIn. Hook inicial + cuerpo en 1-2 párrafos + URL. "
        "Sin hashtags excesivos (máximo 3). Entre 200 y 600 caracteres.\n\n"
        "Título: {title}\nResumen: {excerpt}\nURL: {url}"
    ),
    "instagram": (
        "Genera un caption para Instagram en español para anunciar el siguiente artículo técnico de Azure. "
        "Primer párrafo muy visual e impactante. Luego 2-3 puntos clave del artículo con emojis. "
        "Termina con CTA y la URL. Incluye 15-20 hashtags relevantes separados por línea. "
        "Máximo 2.200 caracteres.\n\n"
        "Título: {title}\nResumen: {excerpt}\nURL: {url}"
    ),
}


class CopyGenerator:
    """Genera copy adaptado por red social usando Azure OpenAI."""

    def __init__(self) -> None:
        self._client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2024-02-01",
        )
        self._model = os.getenv("AZURE_OPENAI_COPY_MODEL", "gpt-4o-mini")

    async def generate(self, item: dict[str, Any], platform: str) -> str:
        prompt_template = _PROMPTS.get(platform)
        if not prompt_template:
            raise ValueError(f"Plataforma no soportada: {platform}")

        prompt = prompt_template.format(
            title=item.get("title", ""),
            excerpt=item.get("excerpt", ""),
            url=item.get("canonical_url", ""),
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
        )
        copy = response.choices[0].message.content or ""
        logger.debug("Copy generado para %s (%d chars): %s...", platform, len(copy), copy[:80])
        return copy.strip()
