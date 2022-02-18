from __future__ import annotations
from homeassistant.components.binary_sensor import (
	BinarySensorDeviceClass,
	BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from .const import (
	DOMAIN,
	DATA_CLIENT,
	DATA_COORDINATOR,
)
from .sorel_connect import (
	SorelConnectCoordinatorEntity,
	SorelConnectEntityType,
)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
	client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
	coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

	entities = []

	mapping = {
		SorelConnectEntityType.ON_OFF: SorelConnectOnOffSensorEntity,
	}

	for entity_type, entity_class in mapping.items():
		if entity_type not in client.entities:
			continue

		for entity in client.entities[entity_type].values():
			entities.append(entity_class(coordinator, entity))

	async_add_entities(entities)


class SorelConnectOnOffSensorEntity(SorelConnectCoordinatorEntity, BinarySensorEntity):

	_attr_device_class = BinarySensorDeviceClass.RUNNING

	def _update_attributes(self) -> None:
		if self.coordinator.data is None:
			return

		self._attr_is_on = self.coordinator.data[self._entity.id] == STATE_ON
