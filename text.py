"""Text entities for Wolink ESL image source input."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.text import TextEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import WolinkEslCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wolink ESL text entities."""
    coordinator: WolinkEslCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WolinkImageSourceText(coordinator)])


class WolinkImageSourceText(TextEntity, RestoreEntity):
    """Stores an image path, URL, or data URL to send to the display."""

    _attr_has_entity_name = True
    _attr_name = "Image Source"
    _attr_icon = "mdi:image-edit-outline"
    _attr_native_max = 65535
    _attr_mode = "text"

    def __init__(self, coordinator: WolinkEslCoordinator) -> None:
        """Initialize the text entity."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_image_source"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
        )

    @property
    def native_value(self) -> str:
        """Return the current image source."""
        return self._coordinator.image_source

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the built-in upload page URL."""
        return {"upload_url": "/api/wolink_esl/upload"}

    async def async_set_value(self, value: str) -> None:
        """Set the image source used by the send image button."""
        self._coordinator.image_source = value.strip()
        self._coordinator._notify_status_listeners()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last configured image source."""
        if (last_state := await self.async_get_last_state()) is not None:
            self._coordinator.image_source = last_state.state or ""
            self._coordinator._notify_status_listeners()
