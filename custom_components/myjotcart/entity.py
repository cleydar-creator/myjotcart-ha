"""Shared bits for MyJotCart entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyJotCartCoordinator


class MyJotCartEntity(CoordinatorEntity[MyJotCartCoordinator]):
    """All entities hang from one device: the household."""

    def __init__(self, coordinator: MyJotCartCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name="MyJotCart",
            manufacturer="Mesh Forge Labs",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.api.url,
        )
