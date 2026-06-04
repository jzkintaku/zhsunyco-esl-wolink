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
from .image_source import async_open_image_source

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
