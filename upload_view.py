"""Authenticated upload and processed-image picker for Wolink ESL images."""

from __future__ import annotations

import html
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import WolinkEslCoordinator
from .image_source import (
    async_open_image_bytes,
    async_open_image_source,
    image_path_for_name,
    list_processed_images,
    safe_image_filename,
)


class WolinkUploadView(HomeAssistantView):
    """Image processing page for configured Wolink ESL displays."""

    url = "/api/wolink_esl/upload"
    name = "api:wolink_esl:upload"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Render the image tool."""
        return web.Response(
            text=self._render_page(request.app["hass"], message=""),
            content_type="text/html",
        )

    async def post(self, request: web.Request) -> web.Response:
        """Process an uploaded image, or send an already processed image."""
        hass = request.app["hass"]
        data = await request.post()
        action = str(data.get("action", "process"))
        entry_id = str(data.get("entry_id", ""))

        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if not isinstance(coordinator, WolinkEslCoordinator):
            return self._response(hass, "Selected device was not found.", status=400)

        if action == "send":
            filename = str(data.get("processed_image", ""))
            if not filename:
                return self._response(hass, "Choose a processed image first.", status=400)
            try:
                pil_image = await async_open_image_source(hass, filename)
                coordinator.image_source = filename
                await coordinator.async_send_image(pil_image)
            except HomeAssistantError as err:
                return self._response(hass, f"Send failed: {err}", status=500)
            except Exception as err:
                return self._response(hass, f"Send failed: {err}", status=500)
            return self._response(
                hass,
                f"Sent {html.escape(filename)} to {coordinator.device_profile['name']}.",
            )

        image_file = data.get("image")
        if image_file is None or not hasattr(image_file, "file"):
            return self._response(hass, "Choose an image file first.", status=400)

        try:
            uploaded = image_file.file.read()
            pil_image = await async_open_image_bytes(hass, uploaded)
            filename = safe_image_filename(getattr(image_file, "filename", "image.png"))
            save_path = image_path_for_name(hass, filename)
            await hass.async_add_executor_job(
                _save_processed_image,
                pil_image,
                save_path,
                coordinator.label_config.width,
                coordinator.label_config.height,
            )
        except Exception as err:
            return self._response(hass, f"Process failed: {err}", status=500)

        return self._response(
            hass,
            f"Processed and saved {save_path.name} "
            f"({coordinator.label_config.width}x{coordinator.label_config.height}).",
        )

    def _response(self, hass, message: str, *, status: int = 200) -> web.Response:
        return web.Response(
            text=self._render_page(hass, message=message),
            content_type="text/html",
            status=status,
        )

    def _render_page(self, hass, *, message: str) -> str:
        coordinators = [
            (entry_id, coordinator)
            for entry_id, coordinator in hass.data.get(DOMAIN, {}).items()
            if isinstance(coordinator, WolinkEslCoordinator)
        ]
        device_options = "\n".join(
            (
                f'<option value="{html.escape(entry_id)}">'
                f'{html.escape(coordinator.device_profile["name"])} '
                f'({html.escape(coordinator.address)})'
                "</option>"
            )
            for entry_id, coordinator in coordinators
        )
        if not device_options:
            device_options = '<option value="">No Wolink ESL devices configured</option>'

        images = list_processed_images(hass)
        image_options = "\n".join(
            f'<option value="{html.escape(filename)}">{html.escape(filename)}</option>'
            for filename in images
        )
        if not image_options:
            image_options = '<option value="">No processed images yet</option>'

        image_list = "\n".join(
            f"<li>{html.escape(filename)}</li>" for filename in images
        ) or "<li>No processed images yet</li>"

        escaped_message = html.escape(message)
        return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Wolink ESL Image Tool</title>
    <style>
      body {{
        font-family: system-ui, sans-serif;
        margin: 24px;
        max-width: 760px;
      }}
      section {{
        border: 1px solid #d0d7de;
        margin: 18px 0;
        padding: 16px;
      }}
      label {{
        display: block;
        font-weight: 600;
        margin: 14px 0 6px;
      }}
      select, input, button {{
        box-sizing: border-box;
        font: inherit;
        width: 100%;
      }}
      select, input {{
        padding: 8px;
      }}
      button {{
        margin-top: 16px;
        padding: 10px 14px;
        cursor: pointer;
      }}
      .message {{
        margin-top: 18px;
        white-space: pre-wrap;
        font-weight: 600;
      }}
      ul {{
        margin-top: 8px;
      }}
    </style>
    <script>
      window.addEventListener("DOMContentLoaded", () => {{
        for (const form of document.querySelectorAll("form")) {{
          form.addEventListener("submit", () => {{
            const button = form.querySelector("button");
            button.disabled = true;
            button.textContent = button.dataset.busy;
          }});
        }}
      }});
    </script>
  </head>
  <body>
    <h1>Wolink ESL Image Tool</h1>

    <section>
      <h2>Process Uploaded Image</h2>
      <form method="post" enctype="multipart/form-data">
        <input type="hidden" name="action" value="process">

        <label for="process_entry_id">Target Size</label>
        <select id="process_entry_id" name="entry_id" required>{device_options}</select>

        <label for="image">Image File</label>
        <input id="image" name="image" type="file" accept="image/*" required>

        <button type="submit" data-busy="Processing...">Process and Save</button>
      </form>
    </section>

    <section>
      <h2>Send Processed Image</h2>
      <form method="post">
        <input type="hidden" name="action" value="send">

        <label for="send_entry_id">Display</label>
        <select id="send_entry_id" name="entry_id" required>{device_options}</select>

        <label for="processed_image">Processed Image</label>
        <select id="processed_image" name="processed_image" required>{image_options}</select>

        <button type="submit" data-busy="Sending...">Upload and Send</button>
      </form>
    </section>

    <section>
      <h2>Processed Images</h2>
      <ul>{image_list}</ul>
    </section>

    <div class="message">{escaped_message}</div>
  </body>
</html>"""


def _save_processed_image(image, path: Path, width: int, height: int) -> None:
    """Resize an uploaded image to the display size and save it as PNG."""
    from PIL import Image, ImageOps

    image = ImageOps.contain(image.convert("RGB"), (width, height))
    canvas = Image.new("RGB", (width, height), "white")
    x = (width - image.width) // 2
    y = (height - image.height) // 2
    canvas.paste(image, (x, y))
    canvas.save(path, "PNG")
