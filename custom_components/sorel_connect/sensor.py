from __future__ import annotations
from homeassistant.components.sensor import (
	SensorDeviceClass,
	SensorEntity,
	SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
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
		SorelConnectEntityType.TEMPERATURE: SorelConnectTemperatureSensorEntity,
		SorelConnectEntityType.PERCENTAGE: SorelConnectPercentageSensorEntity,
	}

	for entity_type, entity_class in mapping.items():
		for entity in client.entities[entity_type].values():
			entities.append(entity_class(coordinator, entity))

	async_add_entities(entities)


class SorelConnectSensorEntity(SorelConnectCoordinatorEntity, SensorEntity):

	_attr_state_class = SensorStateClass.MEASUREMENT

	def _update_attributes(self) -> None:
		if self.coordinator.data is None:
			return

		self._attr_native_value = self.coordinator.data[self._entity.id]


class SorelConnectTemperatureSensorEntity(SorelConnectSensorEntity):

	_attr_device_class = SensorDeviceClass.TEMPERATURE
	_attr_native_unit_of_measurement = TEMP_CELSIUS


class SorelConnectPercentageSensorEntity(SorelConnectSensorEntity):

	_attr_native_unit_of_measurement = PERCENTAGE
