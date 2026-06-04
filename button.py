"""Button entity for Wolink ESL display refresh."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .image_source import async_open_image_source, async_save_processed_image, safe_image_filename

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from .coordinator import WolinkEslCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wolink ESL button entity."""
    coordinator: WolinkEslCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        WolinkRefreshButton(coordinator),
        WolinkSendImageButton(coordinator),
        WolinkProcessImageButton(coordinator),
        WolinkSendProcessedImageButton(coordinator),
    ])


class WolinkRefreshButton(ButtonEntity):
    """Re-sends the last image to the e-paper display."""

    _attr_has_entity_name = True
    _attr_name = "Refresh Display"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: WolinkEslCoordinator) -> None:
        """Initialize the button entity."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
        )

    @property
    def available(self) -> bool:
        """Only enable refresh after an image has been sent in this HA session."""
        return self._coordinator._last_image_bytes is not None

    async def async_added_to_hass(self) -> None:
        """Refresh button availability when the cached image changes."""
        self._coordinator.register_status_listener(self.async_write_ha_state)

    async def async_press(self) -> None:
        """Re-send the last cached image to the device."""
        if self._coordinator._last_image_bytes is None:
            _LOGGER.info(
                "No image to refresh for %s — send an image first",
                self._coordinator.address,
            )
            return

        from PIL import Image

        buf = io.BytesIO(self._coordinator._last_image_bytes)
        pil_image = await self.hass.async_add_executor_job(Image.open, buf)
        await self._coordinator.async_send_image(pil_image)


class WolinkSendImageButton(ButtonEntity):
    """Sends the configured image source to the e-paper display."""

    _attr_has_entity_name = True
    _attr_name = "Send Image"
    _attr_icon = "mdi:image-arrow-up"

    def __init__(self, coordinator: WolinkEslCoordinator) -> None:
        """Initialize the button entity."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_send_image"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
        )

    @property
    def available(self) -> bool:
        """Only enable sending when an image source is configured."""
        return bool(self._coordinator.image_source)

    async def async_added_to_hass(self) -> None:
        """Refresh button availability when the configured image source changes."""
        self._coordinator.register_status_listener(self.async_write_ha_state)

    async def async_press(self) -> None:
        """Send the configured image source to the display."""
        image_source = self._coordinator.image_source
        if not image_source:
            raise HomeAssistantError("Set Image Source before pressing Send Image")

        pil_image = await async_open_image_source(self.hass, image_source)
        await self._coordinator.async_send_image(pil_image)


class WolinkProcessImageButton(ButtonEntity):
    """Processes the configured image source into a stored display-sized PNG."""

    _attr_has_entity_name = True
    _attr_name = "Process Image Source"
    _attr_icon = "mdi:image-size-select-large"

    def __init__(self, coordinator: WolinkEslCoordinator) -> None:
        """Initialize the button entity."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_process_image_source"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
        )

    @property
    def available(self) -> bool:
        """Only enable processing when an image source is configured."""
        return bool(self._coordinator.image_source)

    async def async_added_to_hass(self) -> None:
        """Refresh button availability when the configured image source changes."""
        self._coordinator.register_status_listener(self.async_write_ha_state)

    async def async_press(self) -> None:
        """Process the configured image source and save it to the processed list."""
        image_source = self._coordinator.image_source
        if not image_source:
            raise HomeAssistantError("Set Image Source before processing")

        pil_image = await async_open_image_source(self.hass, image_source)
        filename = safe_image_filename(image_source)
        saved_name = await async_save_processed_image(
            self.hass,
            pil_image,
            filename,
            self._coordinator.label_config.width,
            self._coordinator.label_config.height,
        )
        self._coordinator.processed_image = saved_name
        self._coordinator.image_source = saved_name
        self._coordinator._notify_status_listeners()


class WolinkSendProcessedImageButton(ButtonEntity):
    """Sends the selected processed image to the e-paper display."""

    _attr_has_entity_name = True
    _attr_name = "Send Processed Image"
    _attr_icon = "mdi:image-check"

    def __init__(self, coordinator: WolinkEslCoordinator) -> None:
        """Initialize the button entity."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_send_processed_image"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
        )

    @property
    def available(self) -> bool:
        """Only enable sending when a processed image is selected."""
        return bool(self._coordinator.processed_image)

    async def async_added_to_hass(self) -> None:
        """Refresh button availability when the selected image changes."""
        self._coordinator.register_status_listener(self.async_write_ha_state)

    async def async_press(self) -> None:
        """Send the selected processed image to the display."""
        filename = self._coordinator.processed_image
        if not filename:
            raise HomeAssistantError("Select a Processed Image before sending")

        pil_image = await async_open_image_source(self.hass, filename)
        await self._coordinator.async_send_image(pil_image)
