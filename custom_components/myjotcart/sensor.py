"""Counters for dashboards and automations: what is pending to buy and what is running out at home."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyJotCartConfigEntry
from .coordinator import MyJotCartCoordinator
from .entity import MyJotCartEntity


async def async_setup_entry(hass: HomeAssistant, entry: MyJotCartConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([PendingSensor(coordinator), RunningOutSensor(coordinator)])


class _Base(MyJotCartEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MyJotCartCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.unique_id or coordinator.entry.entry_id}_{key}"


class PendingSensor(_Base):
    """Items still to buy across all lists; per list in the attributes."""

    _attr_icon = "mdi:cart-arrow-down"

    def __init__(self, coordinator: MyJotCartCoordinator) -> None:
        super().__init__(coordinator, "pending")

    @property
    def native_value(self) -> int:
        return sum(1 for i in (self.coordinator.data or {}).get("items", []) if not i.get("done"))

    @property
    def extra_state_attributes(self) -> dict:
        return {
            l["name"]: [i["name"] for i in self.coordinator.items(l["id"]) if not i.get("done")]
            for l in self.coordinator.lists()
        }


class RunningOutSensor(_Base):
    """Products with nothing left at home or below their minimum."""

    _attr_icon = "mdi:fridge-alert-outline"

    def __init__(self, coordinator: MyJotCartCoordinator) -> None:
        super().__init__(coordinator, "running_out")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.low_products())

    @property
    def extra_state_attributes(self) -> dict:
        return {"products": [p["name"] for p in self.coordinator.low_products()]}
