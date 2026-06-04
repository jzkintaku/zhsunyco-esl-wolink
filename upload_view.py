"""Upload and processed-image management page for Wolink ESL images."""

from __future__ import annotations

import base64
import html

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import WolinkEslCoordinator
from .image_source import (
    async_open_image_bytes,
    async_open_image_source,
    async_open_uploaded_image,
    async_save_processed_image,
    async_save_uploaded_image,
    image_path_for_name,
    list_processed_images,
    list_uploaded_images,
    safe_image_filename,
    uploaded_path_for_name,
)


class WolinkUploadView(HomeAssistantView):
    """Image management page for configured Wolink ESL displays."""

    url = "/wolink_esl/upload"
    name = "wolink_esl:upload"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Render the image manager."""
        return self._response(request.app["hass"], "")

    async def post(self, request: web.Request) -> web.Response:
        """Handle uploads, processing, sending, renaming, and deletion."""
        hass = request.app["hass"]
        data = await request.post()
        action = str(data.get("action", "upload"))

        try:
            if action == "upload":
                message = await self._upload_original(hass, data)
            elif action == "process_uploaded":
                message = await self._process_uploaded(hass, data)
            elif action == "send":
                message = await self._send_processed(hass, data)
            elif action == "rename_processed":
                message = self._rename_processed(hass, data)
            elif action == "delete_processed":
                message = self._delete_processed(hass, data)
            elif action == "delete_uploaded":
                message = self._delete_uploaded(hass, data)
            else:
                return self._response(hass, f"Unknown action: {action}", status=400)
        except HomeAssistantError as err:
            return self._response(hass, str(err), status=400)
        except Exception as err:
            return self._response(hass, f"Action failed: {err}", status=500)

        return self._response(hass, message)

    async def _upload_original(self, hass, data) -> str:
        image_file = data.get("image")
        if image_file is None or not hasattr(image_file, "file"):
            raise HomeAssistantError("Choose an image file first.")

        uploaded = image_file.file.read()
        pil_image = await async_open_image_bytes(hass, uploaded)
        filename = safe_image_filename(getattr(image_file, "filename", "image.png"))
        saved_name = await async_save_uploaded_image(hass, pil_image, filename)
        return f"Uploaded original image: {saved_name}"

    async def _process_uploaded(self, hass, data) -> str:
        coordinator = self._coordinator_from_form(hass, data)
        filename = str(data.get("uploaded_image", ""))
        if not filename:
            raise HomeAssistantError("Choose an uploaded image first.")

        pil_image = await async_open_uploaded_image(hass, filename)
        saved_name = await async_save_processed_image(
            hass,
            pil_image,
            filename,
            coordinator.label_config.width,
            coordinator.label_config.height,
        )
        coordinator.processed_image = saved_name
        coordinator.image_source = saved_name
        coordinator._notify_status_listeners()
        return (
            f"Processed {saved_name} "
            f"({coordinator.label_config.width}x{coordinator.label_config.height})."
        )

    async def _send_processed(self, hass, data) -> str:
        coordinator = self._coordinator_from_form(hass, data)
        filename = str(data.get("processed_image", ""))
        if not filename:
            raise HomeAssistantError("Choose a processed image first.")

        pil_image = await async_open_image_source(hass, filename)
        coordinator.processed_image = filename
        coordinator.image_source = filename
        await coordinator.async_send_image(pil_image)
        coordinator._notify_status_listeners()
        return f"Sent {filename} to {coordinator.device_profile['name']}."

    def _rename_processed(self, hass, data) -> str:
        old_name = str(data.get("processed_image", ""))
        new_name = safe_image_filename(str(data.get("new_name", "")))
        if not old_name:
            raise HomeAssistantError("Choose a processed image first.")
        if not new_name:
            raise HomeAssistantError("Enter a new filename.")

        old_path = image_path_for_name(hass, old_name)
        new_path = image_path_for_name(hass, new_name)
        if not old_path.exists():
            raise HomeAssistantError(f"Processed image not found: {old_name}")
        if new_path.exists() and new_path != old_path:
            raise HomeAssistantError(f"Processed image already exists: {new_name}")

        old_path.rename(new_path)
        for coordinator in self._coordinators(hass):
            if coordinator.processed_image == old_name:
                coordinator.processed_image = new_name
            if coordinator.image_source == old_name:
                coordinator.image_source = new_name
            coordinator._notify_status_listeners()
        return f"Renamed {old_name} to {new_name}."

    def _delete_processed(self, hass, data) -> str:
        filename = str(data.get("processed_image", ""))
        if not filename:
            raise HomeAssistantError("Choose a processed image first.")

        path = image_path_for_name(hass, filename)
        if not path.exists():
            raise HomeAssistantError(f"Processed image not found: {filename}")
        path.unlink()
        for coordinator in self._coordinators(hass):
            if coordinator.processed_image == filename:
                coordinator.processed_image = ""
            if coordinator.image_source == filename:
                coordinator.image_source = ""
            coordinator._notify_status_listeners()
        return f"Deleted processed image: {filename}"

    def _delete_uploaded(self, hass, data) -> str:
        filename = str(data.get("uploaded_image", ""))
        if not filename:
            raise HomeAssistantError("Choose an uploaded image first.")

        path = uploaded_path_for_name(hass, filename)
        if not path.exists():
            raise HomeAssistantError(f"Uploaded image not found: {filename}")
        path.unlink()
        return f"Deleted uploaded image: {filename}"

    def _coordinator_from_form(self, hass, data) -> WolinkEslCoordinator:
        entry_id = str(data.get("entry_id", ""))
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if not isinstance(coordinator, WolinkEslCoordinator):
            raise HomeAssistantError("Selected device was not found.")
        return coordinator

    def _coordinators(self, hass) -> list[WolinkEslCoordinator]:
        return [
            coordinator
            for coordinator in hass.data.get(DOMAIN, {}).values()
            if isinstance(coordinator, WolinkEslCoordinator)
        ]

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

        uploaded_cards = self._render_uploaded_cards(hass, device_options)
        processed_cards = self._render_processed_cards(hass, device_options)
        escaped_message = html.escape(message)
        return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Wolink ESL Image Manager</title>
    <style>
      body {{
        background: #f6f8fa;
        color: #1f2328;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0;
      }}
      main {{
        margin: 0 auto;
        max-width: 1180px;
        padding: 24px;
      }}
      h1 {{
        font-size: 28px;
        margin: 0 0 18px;
      }}
      h2 {{
        font-size: 18px;
        margin: 0 0 14px;
      }}
      section {{
        background: #ffffff;
        border: 1px solid #d0d7de;
        margin: 16px 0;
        padding: 16px;
      }}
      label {{
        display: block;
        font-weight: 600;
        margin: 12px 0 6px;
      }}
      select, input, button {{
        box-sizing: border-box;
        font: inherit;
      }}
      select, input[type="text"], input[type="file"] {{
        border: 1px solid #d0d7de;
        padding: 8px;
        width: 100%;
      }}
      button {{
        background: #0969da;
        border: 0;
        color: #ffffff;
        cursor: pointer;
        margin-top: 10px;
        padding: 9px 12px;
      }}
      button.secondary {{
        background: #57606a;
      }}
      button.danger {{
        background: #cf222e;
      }}
      .grid {{
        display: grid;
        gap: 14px;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      }}
      .card {{
        border: 1px solid #d0d7de;
        padding: 12px;
      }}
      .preview {{
        align-items: center;
        background: #ffffff;
        border: 1px solid #d8dee4;
        display: flex;
        height: 190px;
        justify-content: center;
        margin-bottom: 10px;
      }}
      .preview img {{
        max-height: 180px;
        max-width: 100%;
        object-fit: contain;
      }}
      .filename {{
        font-weight: 700;
        overflow-wrap: anywhere;
      }}
      .actions {{
        display: grid;
        gap: 8px;
        margin-top: 10px;
      }}
      .message {{
        color: #0969da;
        font-weight: 700;
        min-height: 24px;
        white-space: pre-wrap;
      }}
      .empty {{
        color: #57606a;
      }}
      @media (max-width: 640px) {{
        main {{
          padding: 14px;
        }}
        .grid {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
    <script>
      window.addEventListener("DOMContentLoaded", () => {{
        const uploadInput = document.getElementById("image");
        const uploadPreview = document.getElementById("upload-preview");
        if (uploadInput && uploadPreview) {{
          uploadInput.addEventListener("change", () => {{
            const file = uploadInput.files && uploadInput.files[0];
            if (!file) {{
              uploadPreview.innerHTML = "";
              return;
            }}
            const url = URL.createObjectURL(file);
            uploadPreview.innerHTML = `<img src="${{url}}" alt="">`;
          }});
        }}
        for (const form of document.querySelectorAll("form")) {{
          form.addEventListener("submit", () => {{
            const button = form.querySelector("button[type='submit']");
            if (!button) return;
            button.disabled = true;
            button.textContent = button.dataset.busy || "Working...";
          }});
        }}
      }});
    </script>
  </head>
  <body>
    <main>
      <h1>Wolink ESL Image Manager</h1>
      <div class="message">{escaped_message}</div>

      <section>
        <h2>Upload Original Image</h2>
        <form method="post" enctype="multipart/form-data">
          <input type="hidden" name="action" value="upload">
          <label for="image">Image File</label>
          <input id="image" name="image" type="file" accept="image/*" required>
          <div id="upload-preview" class="preview"></div>
          <button type="submit" data-busy="Uploading...">Upload</button>
        </form>
      </section>

      <section>
        <h2>Uploaded Images</h2>
        {uploaded_cards}
      </section>

      <section>
        <h2>Processed Images</h2>
        {processed_cards}
      </section>
    </main>
  </body>
</html>"""

    def _render_uploaded_cards(self, hass, device_options: str) -> str:
        filenames = list_uploaded_images(hass)
        if not filenames:
            return '<p class="empty">No uploaded images yet.</p>'

        cards = []
        for filename in filenames:
            escaped = html.escape(filename)
            preview = self._preview_for_path(uploaded_path_for_name(hass, filename))
            cards.append(
                f"""<div class="card">
          <div class="preview">{preview}</div>
          <div class="filename">{escaped}</div>
          <div class="actions">
            <form method="post">
              <input type="hidden" name="action" value="process_uploaded">
              <input type="hidden" name="uploaded_image" value="{escaped}">
              <label>Target Display</label>
              <select name="entry_id" required>{device_options}</select>
              <button type="submit" data-busy="Processing...">Process to Display Size</button>
            </form>
            <form method="post" onsubmit="return confirm('Delete uploaded image {escaped}?')">
              <input type="hidden" name="action" value="delete_uploaded">
              <input type="hidden" name="uploaded_image" value="{escaped}">
              <button class="danger" type="submit" data-busy="Deleting...">Delete Uploaded Image</button>
            </form>
          </div>
        </div>"""
            )
        return f'<div class="grid">{"".join(cards)}</div>'

    def _render_processed_cards(self, hass, device_options: str) -> str:
        filenames = list_processed_images(hass)
        if not filenames:
            return '<p class="empty">No processed images yet.</p>'

        cards = []
        for filename in filenames:
            escaped = html.escape(filename)
            preview = self._preview_for_path(image_path_for_name(hass, filename))
            cards.append(
                f"""<div class="card">
          <div class="preview">{preview}</div>
          <div class="filename">{escaped}</div>
          <div class="actions">
            <form method="post">
              <input type="hidden" name="action" value="send">
              <input type="hidden" name="processed_image" value="{escaped}">
              <label>Display</label>
              <select name="entry_id" required>{device_options}</select>
              <button type="submit" data-busy="Sending...">Send to Display</button>
            </form>
            <form method="post">
              <input type="hidden" name="action" value="rename_processed">
              <input type="hidden" name="processed_image" value="{escaped}">
              <label>New Filename</label>
              <input type="text" name="new_name" value="{escaped}" required>
              <button class="secondary" type="submit" data-busy="Renaming...">Rename</button>
            </form>
            <form method="post" onsubmit="return confirm('Delete processed image {escaped}?')">
              <input type="hidden" name="action" value="delete_processed">
              <input type="hidden" name="processed_image" value="{escaped}">
              <button class="danger" type="submit" data-busy="Deleting...">Delete Processed Image</button>
            </form>
          </div>
        </div>"""
            )
        return f'<div class="grid">{"".join(cards)}</div>'

    def _preview_for_path(self, path) -> str:
        if not path.exists():
            return '<span class="empty">Missing file</span>'
        data = base64.b64encode(path.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{data}" alt="">'
