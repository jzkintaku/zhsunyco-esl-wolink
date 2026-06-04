"""Helpers for loading image sources for Wolink ESL displays."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession


IMAGE_DIR = "wolink_esl_images"
UPLOAD_DIR = "wolink_esl_uploads"
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def image_storage_dir(hass) -> Path:
    """Return the directory used for processed Wolink ESL images."""
    path = Path(hass.config.path(IMAGE_DIR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def upload_storage_dir(hass) -> Path:
    """Return the directory used for uploaded original Wolink ESL images."""
    path = Path(hass.config.path(UPLOAD_DIR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_image_filename(filename: str) -> str:
    """Return a safe PNG filename for saved processed images."""
    stem = Path(filename).stem.strip() or "image"
    stem = _SAFE_FILENAME.sub("_", stem).strip("._") or "image"
    return f"{stem}.png"


def image_path_for_name(hass, filename: str) -> Path:
    """Resolve a stored image filename without allowing path traversal."""
    safe_name = safe_image_filename(filename)
    return image_storage_dir(hass) / safe_name


def uploaded_path_for_name(hass, filename: str) -> Path:
    """Resolve an uploaded image filename without allowing path traversal."""
    safe_name = safe_image_filename(filename)
    return upload_storage_dir(hass) / safe_name


def list_processed_images(hass) -> list[str]:
    """List processed image filenames."""
    return sorted(path.name for path in image_storage_dir(hass).glob("*.png"))


def list_uploaded_images(hass) -> list[str]:
    """List uploaded original image filenames."""
    return sorted(path.name for path in upload_storage_dir(hass).glob("*.png"))


async def async_save_processed_image(hass, image, filename: str, width: int, height: int) -> str:
    """Resize an image to the display size, save it, and return its filename."""
    safe_name = safe_image_filename(filename)
    save_path = image_path_for_name(hass, safe_name)
    await hass.async_add_executor_job(
        _save_processed_image,
        image,
        save_path,
        width,
        height,
    )
    return safe_name


async def async_save_uploaded_image(hass, image, filename: str) -> str:
    """Save an uploaded original image as PNG and return its filename."""
    safe_name = safe_image_filename(filename)
    save_path = uploaded_path_for_name(hass, safe_name)
    await hass.async_add_executor_job(_save_uploaded_image, image, save_path)
    return safe_name


async def async_open_uploaded_image(hass, filename: str):
    """Open a previously uploaded original image by filename."""
    return await hass.async_add_executor_job(
        _open_image_path,
        str(uploaded_path_for_name(hass, filename)),
    )


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

    if not any(sep in source for sep in ("/", "\\")):
        return await hass.async_add_executor_job(_open_image_path, str(image_path_for_name(hass, source)))

    return await hass.async_add_executor_job(_open_image_path, source)


async def async_open_image_bytes(hass, data: bytes):
    """Open an image from uploaded bytes."""
    return await hass.async_add_executor_job(_open_image_bytes, data)


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


def _save_processed_image(image, path: Path, width: int, height: int) -> None:
    """Resize an uploaded image to the display size and save it as PNG."""
    from PIL import Image, ImageOps

    image = ImageOps.contain(image.convert("RGB"), (width, height))
    canvas = Image.new("RGB", (width, height), "white")
    x = (width - image.width) // 2
    y = (height - image.height) // 2
    canvas.paste(image, (x, y))
    canvas.save(path, "PNG")


def _save_uploaded_image(image, path: Path) -> None:
    """Save an uploaded image as a normalized RGB PNG."""
    image.convert("RGB").save(path, "PNG")
