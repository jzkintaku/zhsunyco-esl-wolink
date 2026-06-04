"""Authenticated upload page for Wolink ESL images."""

from __future__ import annotations

import html

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import WolinkEslCoordinator
from .image_source import async_open_image_bytes


class WolinkUploadView(HomeAssistantView):
    """Small HTML upload form for sending an image to a configured display."""

    url = "/api/wolink_esl/upload"
    name = "api:wolink_esl:upload"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Render the upload form."""
        return web.Response(
            text=self._render_page(request.app["hass"], message=""),
            content_type="text/html",
        )

    async def post(self, request: web.Request) -> web.Response:
        """Handle an uploaded image and send it to the selected display."""
        hass = request.app["hass"]
        data = await request.post()
        entry_id = str(data.get("entry_id", ""))
        image_file = data.get("image")

        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if not isinstance(coordinator, WolinkEslCoordinator):
            return web.Response(
                text=self._render_page(hass, message="Selected device was not found."),
                content_type="text/html",
                status=400,
            )

        if image_file is None or not hasattr(image_file, "file"):
            return web.Response(
                text=self._render_page(hass, message="Choose an image file first."),
                content_type="text/html",
                status=400,
            )

        try:
            uploaded = image_file.file.read()
            pil_image = await async_open_image_bytes(hass, uploaded)
            await coordinator.async_send_image(pil_image)
        except HomeAssistantError as err:
            message = f"Send failed: {err}"
            status = 500
        except Exception as err:
            message = f"Send failed: {err}"
            status = 500
        else:
            message = f"Sent image to {coordinator.device_profile['name']}."
            status = 200

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
        options = "\n".join(
            (
                f'<option value="{html.escape(entry_id)}">'
                f'{html.escape(coordinator.device_profile["name"])} '
                f'({html.escape(coordinator.address)})'
                "</option>"
            )
            for entry_id, coordinator in coordinators
        )
        if not options:
            options = '<option value="">No Wolink ESL devices configured</option>'

        escaped_message = html.escape(message)
        return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Wolink ESL Upload</title>
    <style>
      body {{
        font-family: system-ui, sans-serif;
        margin: 24px;
        max-width: 560px;
      }}
      label {{
        display: block;
        font-weight: 600;
        margin: 16px 0 6px;
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
        margin-top: 20px;
        padding: 10px 14px;
        cursor: pointer;
      }}
      .message {{
        margin-top: 18px;
        white-space: pre-wrap;
      }}
    </style>
  </head>
  <body>
    <h1>Wolink ESL Upload</h1>
    <form method="post" enctype="multipart/form-data">
      <label for="entry_id">Display</label>
      <select id="entry_id" name="entry_id" required>{options}</select>

      <label for="image">Image</label>
      <input id="image" name="image" type="file" accept="image/*" required>

      <button type="submit">Upload and Send</button>
    </form>
    <div class="message">{escaped_message}</div>
  </body>
</html>"""
