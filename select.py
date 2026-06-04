"""Select entities for Wolink ESL processed images."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .image_source import list_processed_images

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import WolinkEslCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wolink ESL select entities."""
    coordinator: WolinkEslCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WolinkProcessedImageSelect(coordinator)])


class WolinkProcessedImageSelect(SelectEntity, RestoreEntity):
    """Selects a processed image filename to send."""

    _attr_has_entity_name = True
    _attr_name = "Processed Image"
    _attr_icon = "mdi:image-multiple"

    def __init__(self, coordinator: WolinkEslCoordinator) -> None:
        """Initialize the select entity."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_processed_image"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
        )

    @property
    def options(self) -> list[str]:
        """Return processed image filenames."""
        return list_processed_images(self.hass)

    @property
    def current_option(self) -> str | None:
        """Return the selected processed image filename."""
        if self._coordinator.processed_image in self.options:
            return self._coordinator.processed_image
        return self.options[0] if self.options else None

    async def async_select_option(self, option: str) -> None:
        """Select a processed image filename."""
        self._coordinator.processed_image = option
        self._coordinator.image_source = option
        self._coordinator._notify_status_listeners()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last selected processed image."""
        if (last_state := await self.async_get_last_state()) is not None:
            option = last_state.state
            if option in self.options:
                self._coordinator.processed_image = option
                self._coordinator.image_source = option
        self._coordinator.register_status_listener(self.async_write_ha_state)
