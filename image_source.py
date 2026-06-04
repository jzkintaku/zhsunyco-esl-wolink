"""Helpers for loading image sources for Wolink ESL displays."""

from __future__ import annotations

import base64
import io

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def async_open_image_source(hass, source: str):
    """Open an image from a local path, HTTP(S) URL, or data URL."""
    source = source.strip()
    if not source:
        raise HomeAssistantError("Image source is empty")

    if source.startswith(("http://", "https://")):
        session = async_get_clientsession(hass)
        try:
            async with session.get(source) as response:
                if response.status >= 400:
                    raise HomeAssistantError(
                        f"Failed to download image: HTTP {response.status}"
                    )
                data = await response.read()
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(f"Failed to download image: {err}") from err
        return await hass.async_add_executor_job(_open_image_bytes, data)

    if source.startswith("data:image/"):
        try:
            _header, encoded = source.split(",", 1)
            data = base64.b64decode(encoded)
        except Exception as err:
            raise HomeAssistantError(f"Failed to decode image data URL: {err}") from err
        return await hass.async_add_executor_job(_open_image_bytes, data)

    return await hass.async_add_executor_job(_open_image_path, source)


def _open_image_bytes(data: bytes):
    from PIL import Image

    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def _open_image_path(path: str):
    from PIL import Image

    image = Image.open(path)
    image.load()
    return image
